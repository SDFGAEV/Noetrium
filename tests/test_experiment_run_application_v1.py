from __future__ import annotations

from types import SimpleNamespace

import pytest

from noetrium_platform.research.experimentation.run.api import ExperimentRunSpec
from noetrium_platform.research.experimentation.run.runtime import ExperimentRunApplication
from noetrium_platform.research.experimentation.run.runtime.decision_coordination import (
    DecisionCycleCoordinator,
    _CycleState,
)
from noetrium_platform.research.experimentation.run.runtime.resources import RunResourceAcquirer
from noetrium_platform.research.experimentation.study.api import (
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
from noetrium_platform.research.experimentation.study.runtime import (
    BasicStudyMetricAggregator,
    DeterministicStudyAssignment,
    StudyMatrixExecutor,
)
from noetrium_platform.foundation.kernel.kernel import ExecutionContext, canonical_digest


class _Publication:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def publish_protocol(self, protocol, assignments):
        del protocol, assignments
        self.calls.append("protocol")
        return "protocol"

    def publish_observations(self, observations):
        del observations
        self.calls.append("observations")
        return "observations"

    def publish_aggregates(self, aggregates):
        del aggregates
        self.calls.append("aggregates")
        return "aggregates"


class _UnitAdapter:
    def execute(self, unit):
        return tuple(
            StudyMetricObservation(assignment, (("score", float(unit.repetition + 1)),))
            for assignment in unit.assignments
        )


def test_run_parent_owns_study_expansion_execution_and_publication() -> None:
    protocol = StudyProtocol(
        study_id="study-1",
        workload_id="workload-1",
        variants=(
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        repetitions=2,
        seed_schedule_digest="c" * 64,
        metric_names=("score",),
        task_manifest_digest="d" * 64,
    )
    run_spec = ExperimentRunSpec(
        run_id="run-1",
        project_id="project-1",
        experiment_id="experiment-1",
        study_id=protocol.study_id,
        execution_profile="test",
        task_manifest_digest=protocol.task_manifest_digest,
        seed_schedule_digest=protocol.seed_schedule_digest,
        repetitions=protocol.repetitions,
        artifact_root="runs/run-1",
        environment_identity_digest=canonical_digest("environment"),
    )
    publication = _Publication()
    application = ExperimentRunApplication(
        assignments=DeterministicStudyAssignment(),
        matrix=StudyMatrixExecutor(BasicStudyMetricAggregator()),
        publication=publication,
    )

    result = application.execute(
        run_spec=run_spec,
        protocol=protocol,
        unit_adapter=_UnitAdapter(),
    )

    assert result.run_spec_digest == run_spec.identity_digest()
    assert result.protocol_digest == protocol.protocol_digest
    assert len(result.study_report.observations) == 4
    assert publication.calls == ["protocol", "observations", "aggregates"]


class _NoneBinder:
    def bind(self, spec, context):
        return None


class _EmptyBinder:
    def bind(self, spec, context):
        return SimpleNamespace(operation_results=(), participants=())


class _NoopLifecycle:
    def open_participant(self, *args, **kwargs):
        raise AssertionError("participant lifecycle must not run")

    def close_participant(self, *args, **kwargs):
        raise AssertionError("participant lifecycle must not run")


class _NoneScientific:
    def execute(self, **kwargs):
        return None


def _context() -> ExecutionContext:
    return ExecutionContext("run", "trace", "span", study_id="study")


def test_run_resource_acquirer_rejects_missing_binding_explicitly() -> None:
    acquirer = RunResourceAcquirer(_NoneBinder(), _NoopLifecycle())
    identity = SimpleNamespace(run_id="run", trace_id="trace", session_id="session")
    spec = SimpleNamespace(study_id="study")
    with pytest.raises(RuntimeError, match="binder returned no bound participants"):
        acquirer.acquire(spec, identity)


def test_decision_cycle_rejects_missing_binding_before_dereference() -> None:
    coordinator = DecisionCycleCoordinator(_NoneBinder(), _NoopLifecycle(), _NoneScientific())
    state = _CycleState(_context())
    with pytest.raises(RuntimeError, match="binder returned no bound participants"):
        coordinator._execute(
            state, object(), SimpleNamespace(session_id="session"),
            task=object(), input_kind="test", input_payload=None,
        )


def test_decision_cycle_rejects_missing_scientific_execution_explicitly() -> None:
    coordinator = DecisionCycleCoordinator(_EmptyBinder(), _NoopLifecycle(), _NoneScientific())
    state = _CycleState(_context())
    with pytest.raises(RuntimeError, match="scientific executor returned no execution result"):
        coordinator._execute(
            state, object(), SimpleNamespace(session_id="session"),
            task=object(), input_kind="test", input_payload=None,
        )


def test_experiment_run_rejects_plan_without_protocol_explicitly() -> None:
    application = ExperimentRunApplication(
        assignments=object(), matrix=object(), publication=object()
    )
    with pytest.raises(RuntimeError, match="protocol resolution failed"):
        application.execute(
            run_spec=object(),
            plan=SimpleNamespace(protocol=None),
            unit_adapter=object(),
        )
