from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from uuid import uuid4

from noetrium_platform.foundation.kernel.concurrency.api import (
    Deadline,
    ExecutionLaneKind,
    ExecutionSpec,
    TaskFailureScope,
    TaskGroupPort,
)

from ..api import (
    BoundStudyUnitExecutionPort,
    ExperimentPlan,
    StudyAssignment,
    StudyExecutionUnit,
    StudyMatrixExecutionReport,
    StudyMetricAggregationPort,
    StudyMetricObservation,
    StudyProtocol,
    StudyUnitExecutionPort,
    VariantBinding,
)
from .protocol import DeterministicStudyAssignment


def _study_units(
    protocol: StudyProtocol,
    assignments: tuple[StudyAssignment, ...],
) -> tuple[StudyExecutionUnit, ...]:
    grouped: dict[int, list[StudyAssignment]] = defaultdict(list)
    for assignment in assignments:
        grouped[assignment.repetition].append(assignment)
    return tuple(
        StudyExecutionUnit(
            protocol.study_id,
            repetition,
            tuple(sorted(grouped[repetition], key=lambda item: (item.variant_id, item.seed))),
        )
        for repetition in sorted(grouped)
    )


def _binding_index(plan: ExperimentPlan) -> dict[str, VariantBinding]:
    return {item.variant.variant_id: item for item in plan.bindings}


class StudyMatrixExecutor:
    """Run every declared assignment through one injected environment adapter.

    Matrix completeness, repetition grouping and aggregate invocation are
    platform responsibilities. The adapter owns environment and branch
    mechanics only.
    """

    def __init__(
        self,
        aggregation: StudyMetricAggregationPort,
        assignment_expander: DeterministicStudyAssignment | None = None,
        task_group: TaskGroupPort | None = None,
    ) -> None:
        self._aggregation = aggregation
        self._assignment_expander = assignment_expander or DeterministicStudyAssignment()
        self._task_group = task_group

    def _execute_repetitions(
        self,
        protocol: StudyProtocol,
        units: tuple[StudyExecutionUnit, ...],
        execute_one: Callable[[StudyExecutionUnit], tuple[StudyMetricObservation, ...]],
    ) -> tuple[tuple[StudyExecutionUnit, tuple[StudyMetricObservation, ...]], ...]:
        """Execute repetition units with an explicit rolling fanout window.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: Each repetition unit is submitted exactly once and each resulting handle is joined exactly once; the nested rolling-window loops partition the unit sequence into bounded batches rather than rescanning prior units.
        Concurrency-Policy: BOUNDED_TASK_FANOUT
        Concurrency-Rationale: The active child-task window never exceeds the frozen max_parallel_repetitions scientific policy, and each child receives the frozen repetition timeout as a deadline.
        """
        parallelism = protocol.concurrency_policy.max_parallel_repetitions
        if parallelism == 1:
            return tuple((unit, execute_one(unit)) for unit in units)
        if self._task_group is None:
            raise RuntimeError(
                "parallel study repetitions require an injected structured task group"
            )

        invocation_id = uuid4().hex
        completed: list[tuple[StudyExecutionUnit, tuple[StudyMetricObservation, ...]]] = []
        next_index = 0
        while next_index < len(units):
            handles = []
            while len(handles) < parallelism and next_index < len(units):
                unit = units[next_index]
                next_index += 1

                def run(_context, owned_unit=unit):
                    return execute_one(owned_unit)

                repetition_deadline = Deadline.after(protocol.concurrency_policy.repetition_timeout_seconds)
                handle = self._task_group.submit(
                    ExecutionSpec(
                        task_id=(
                            f"study-repetition:{protocol.study_id}:{invocation_id}:"
                            f"{unit.repetition}"
                        ),
                        lane_kind=ExecutionLaneKind.BLOCKING_IO,
                        failure_scope=TaskFailureScope.CALLER,
                    ),
                    run,
                    deadline=repetition_deadline,
                )
                handles.append((unit, handle))
            errors: list[BaseException] = []
            for unit, handle in handles:
                try:
                    observations = tuple(
                        handle.result(timeout=protocol.concurrency_policy.repetition_timeout_seconds)
                    )
                except BaseException as exc:
                    errors.append(exc)
                else:
                    completed.append((unit, observations))
            if errors:
                raise ExceptionGroup(
                    f"parallel study repetition batch failed: study={protocol.study_id}",
                    errors,
                )
        return tuple(sorted(completed, key=lambda item: item[0].repetition))

    def execute(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
        adapter: StudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport:
        expected = self._assignment_expander.assignments(protocol)
        self._require_exact_assignments(expected, assignments)
        units = _study_units(protocol, assignments)
        observations: list[StudyMetricObservation] = []
        for unit, unit_observations in self._execute_repetitions(
            protocol, units, lambda owned: tuple(adapter.execute(owned))
        ):
            self._require_exact_observations(unit, unit_observations, unit.repetition)
            observations.extend(sorted(unit_observations, key=lambda item: item.assignment.variant_id))

        frozen_observations = tuple(observations)
        aggregates = self._aggregation.aggregate(protocol, frozen_observations, expected)
        return StudyMatrixExecutionReport(protocol.protocol_digest, frozen_observations, aggregates)

    def execute_plan(
        self,
        plan: ExperimentPlan,
        assignments: tuple[StudyAssignment, ...],
        adapter: BoundStudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport:
        """Execute a compiled plan through its complete binding set.

        This is intentionally a distinct port from the legacy protocol-only
        path. A plan run must not silently downgrade to an adapter that can
        only interpret ``control`` and ``treatment`` by kind.
        """

        plan.assert_consistent()
        execute_bound = getattr(adapter, "execute_bound", None)
        if not callable(execute_bound):
            raise TypeError(
                "compiled experiment plans require an adapter implementing execute_bound"
            )
        expected = plan.assignments
        self._require_exact_assignments(expected, assignments)
        units = _study_units(plan.protocol, assignments)
        binding_index = _binding_index(plan)

        def execute_unit(unit: StudyExecutionUnit) -> tuple[StudyMetricObservation, ...]:
            unit_bindings = tuple(binding_index[item.variant_id] for item in unit.assignments)
            return tuple(execute_bound(unit, unit_bindings, plan.plan_digest))

        observations: list[StudyMetricObservation] = []
        for unit, unit_observations in self._execute_repetitions(
            plan.protocol, units, execute_unit
        ):
            self._require_exact_observations(unit, unit_observations, unit.repetition)
            observations.extend(sorted(unit_observations, key=lambda item: item.assignment.variant_id))

        frozen_observations = tuple(observations)
        aggregates = self._aggregation.aggregate(plan.protocol, frozen_observations, plan.assignments)
        return StudyMatrixExecutionReport(
            plan.protocol.protocol_digest,
            frozen_observations,
            aggregates,
            binding_digest=plan.binding_digest,
            plan_digest=plan.plan_digest,
        )

    @staticmethod
    def _require_exact_observations(
        unit: StudyExecutionUnit,
        observations: tuple[StudyMetricObservation, ...],
        repetition: int,
    ) -> None:
        expected_digests = {item.assignment_digest for item in unit.assignments}
        actual_digests = tuple(item.assignment.assignment_digest for item in observations)
        if len(actual_digests) != len(set(actual_digests)):
            raise ValueError(f"study unit returned duplicate observations: repetition={repetition}")
        if set(actual_digests) != expected_digests:
            raise ValueError(
                "study unit did not return exactly one observation per assignment: "
                f"repetition={repetition}"
            )

    @staticmethod
    def _require_exact_assignments(
        expected: tuple[StudyAssignment, ...],
        actual: tuple[StudyAssignment, ...],
    ) -> None:
        expected_digests = tuple(item.assignment_digest for item in expected)
        actual_digests = tuple(item.assignment_digest for item in actual)
        if len(actual_digests) != len(set(actual_digests)):
            raise ValueError("study assignment matrix contains duplicate assignments")
        if set(expected_digests) != set(actual_digests):
            raise ValueError("study assignment matrix is not exactly the declared protocol")


__all__ = ["StudyMatrixExecutor"]
