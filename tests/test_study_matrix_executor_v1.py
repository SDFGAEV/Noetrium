from unittest.mock import patch
from threading import Lock
import time

import pytest

from research_platform.experimentation.study.runtime import BasicStudyMetricAggregator, DeterministicStudyAssignment, StudyMatrixExecutor

from research_platform.platform.concurrency.api import ConcurrencyBudget, TaskFailurePolicy
from research_platform.platform.concurrency.composition import build_concurrency_runtime
from research_platform.experimentation.study.api import (
    ExperimentPlan,
    StudyConcurrencyPolicy,
    StudyExecutionUnit,
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantBinding,
    VariantKind,
)


def _protocol() -> StudyProtocol:
    return StudyProtocol(
        "study-matrix",
        "workload-matrix",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        2,
        "c" * 64,
        ("score",),
        "d" * 64,
    )


class _Adapter:
    def execute(self, unit: StudyExecutionUnit):
        return tuple(
            StudyMetricObservation(assignment, (("score", float(unit.repetition + 1)),))
            for assignment in unit.assignments
        )


def test_matrix_executor_groups_repetitions_and_returns_complete_report() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    report = StudyMatrixExecutor(BasicStudyMetricAggregator()).execute(
        protocol,
        assignments,
        _Adapter(),
    )
    assert report.protocol_digest == protocol.protocol_digest
    assert len(report.observations) == 4
    assert {(item.variant_id, item.count) for item in report.aggregates} == {
        ("control", 2),
        ("treatment", 2),
    }



def test_parallel_repetition_policy_uses_structured_concurrency_and_deterministic_merge() -> None:
    protocol = StudyProtocol(
        "study-parallel",
        "workload-parallel",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        4,
        "c" * 64,
        ("score",),
        "d" * 64,
        concurrency_policy=StudyConcurrencyPolicy(max_parallel_repetitions=2),
    )
    assignments = DeterministicStudyAssignment().assignments(protocol)
    runtime = build_concurrency_runtime(
        budget=ConcurrencyBudget(
            max_blocking_io_workers=2,
            max_cpu_workers=1,
            default_queue_capacity=4,
        )
    )
    group = runtime.open_task_group("study-parallel-execution", failure_policy=TaskFailurePolicy.COLLECT_ALL)
    active = 0
    max_active = 0
    lock = Lock()

    class ParallelAdapter:
        def execute(self, unit: StudyExecutionUnit):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.04)
                return tuple(
                    StudyMetricObservation(
                        assignment,
                        (("score", float(unit.repetition + 1)),),
                    )
                    for assignment in unit.assignments
                )
            finally:
                with lock:
                    active -= 1

    try:
        report = StudyMatrixExecutor(
            BasicStudyMetricAggregator(),
            task_group=group,
        ).execute(protocol, assignments, ParallelAdapter())
        assert max_active == 2
        assert [item.assignment.repetition for item in report.observations] == [0, 0, 1, 1, 2, 2, 3, 3]
        assert [item.assignment.variant_id for item in report.observations[:2]] == ["control", "treatment"]
    finally:
        group.close()
        runtime.close()


def test_scientific_concurrency_policy_is_part_of_protocol_identity() -> None:
    serial = _protocol()
    parallel = StudyProtocol(
        serial.study_id,
        serial.workload_id,
        serial.variants,
        serial.repetitions,
        serial.seed_schedule_digest,
        serial.metric_names,
        serial.task_manifest_digest,
        concurrency_policy=StudyConcurrencyPolicy(max_parallel_repetitions=2),
    )
    assert serial.protocol_digest != parallel.protocol_digest


def test_execute_plan_uses_binding_index_instead_of_repeated_linear_lookup():
    protocol = _protocol()
    bindings = tuple(
        VariantBinding(v, "e" * 64, f"provider-{v.variant_id}", "none", v.kind.value)
        for v in protocol.variants
    )
    assignments = DeterministicStudyAssignment().assignments(protocol)
    plan = ExperimentPlan.compile(protocol, bindings, assignments)

    class BoundAdapter:
        def execute_bound(self, unit, unit_bindings, plan_digest):
            assert plan_digest == plan.plan_digest
            assert tuple(b.variant.variant_id for b in unit_bindings) == tuple(a.variant_id for a in unit.assignments)
            return tuple(StudyMetricObservation(a, (("score", 1.0),)) for a in unit.assignments)

    with patch.object(
        ExperimentPlan,
        "binding_for",
        side_effect=AssertionError("execute_plan performed a linear binding scan"),
    ):
        report = StudyMatrixExecutor(BasicStudyMetricAggregator()).execute_plan(
            plan, assignments, BoundAdapter()
        )
    assert len(report.observations) == len(assignments)

def test_plan_rejects_binding_order_that_diverges_from_protocol():
    protocol = _protocol()
    bindings = tuple(
        VariantBinding(v, "e" * 64, f"provider-{v.variant_id}", "none", v.kind.value)
        for v in protocol.variants
    )
    assignments = DeterministicStudyAssignment().assignments(protocol)
    with pytest.raises(ValueError, match="variant order"):
        ExperimentPlan.compile(protocol, tuple(reversed(bindings)), assignments)


def test_assignment_order_is_frozen_plan_authority_not_implicitly_sorted():
    protocol = _protocol()
    bindings = tuple(
        VariantBinding(v, "e" * 64, f"provider-{v.variant_id}", "none", v.kind.value)
        for v in protocol.variants
    )
    assignments = DeterministicStudyAssignment().assignments(protocol)
    forward = ExperimentPlan.compile(protocol, bindings, assignments)
    reversed_plan = ExperimentPlan.compile(protocol, bindings, tuple(reversed(assignments)))
    assert forward.assignment_digest != reversed_plan.assignment_digest
    assert forward.plan_digest != reversed_plan.plan_digest
