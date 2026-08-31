from __future__ import annotations

from dataclasses import dataclass

import pytest

from research_platform.artifact.reference.api import ArtifactReference
from research_platform.experimentation.api import (
    ResearchBindingContribution, ResearchBindingRequirements,
    ResearchParticipantRequirement, resolve_research_requirements,
)
from research_platform.experimentation.experiment.api import (
    ExperimentParticipantSpec, ExperimentTrialProtocolIdentity,
)
from research_platform.experimentation.study.api import (
    BenchmarkTaskSet, FactorLevelSpec, MeasurementDefinition,
    MeasurementProtocol, MeasurementRecord, MeasurementValue,
    MeasurementValueKind, ResearchRevision, ResearchStudyDefinition,
    StudyFactorSpec, TaskDefinition, TrialExecutionReceipt, compile_research_plan,
)
from research_platform.experimentation.study.api import compile_research_plan
from research_platform.experimentation.study.runtime import TrialMatrixExecutor
from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity, ParticipantSessionRuntimeIdentity,
)
from research_platform.scope.api import ScopeIdentity, ScopeKind


@dataclass(frozen=True)
class _Identity:
    project_id: str


@dataclass(frozen=True)
class _Capability:
    requirement_id: str


@dataclass(frozen=True)
class _Method:
    method_id: str
    treatment_id: str


@dataclass(frozen=True)
class _Manifest:
    identity: _Identity
    semantic_digest: str
    capability_requirements: tuple[_Capability, ...]
    method_requirements: tuple[_Method, ...]
    configuration_refs: tuple[object, ...] = ()


AGENT_CFG = "1" * 64
OFFLINE_CFG = "2" * 64
CUSTOM_CFG = "3" * 64


def _participant(role: str, kind: str, *, depends_on_roles: tuple[str, ...] = ()) -> ExperimentParticipantSpec:
    return ExperimentParticipantSpec(
        role,
        ParticipantImplementationIdentity(kind, f"{kind}-impl", "1", "1", "1", "a" * 64),
        ParticipantSessionRuntimeIdentity(f"runtime.{kind}", "1", "1", "b" * 64),
        "d" * 64,
        depends_on_roles,
    )


def _benchmark() -> BenchmarkTaskSet:
    task = TaskDefinition("task-1", "1", "generic", "task.v1", "a" * 64)
    return BenchmarkTaskSet("benchmark", "1", "b" * 64, "task.v1", (task,))


def _measurements() -> MeasurementProtocol:
    return MeasurementProtocol(
        "trial-measurements",
        (
            MeasurementDefinition("score", "scalar-v1", MeasurementValueKind.SCALAR),
            MeasurementDefinition("trace", "trace-v1", MeasurementValueKind.STRUCTURED),
        ),
    )


def _plan(protocol_identity, participants, revision):
    requirements = ResearchBindingRequirements(
        "trial-provider",
        participants=tuple(
            ResearchParticipantRequirement(
                row.role, row.implementation.kind, "method", row.role,
                depends_on_roles=row.depends_on_roles,
            )
            for row in participants
        ),
    )
    definition = ResearchStudyDefinition(
        "project", "experiment", "study", "workload",
        (
            StudyFactorSpec(
                "mode",
                (
                    FactorLevelSpec("control", "control", control=True),
                    FactorLevelSpec("candidate", "candidate"),
                ),
            ),
        ),
        ("seed-1",), 1, _measurements(), _benchmark(), None,
        requirements, protocol_identity, revision,
    )
    manifest = _Manifest(
        _Identity("project"), "9" * 64,
        (_Capability("trial-provider"),),
        tuple(_Method("method", row.role) for row in participants),
    )
    resolution = resolve_research_requirements(definition, manifest)
    binding = ResearchBindingContribution(
        resolution.resolution_digest,
        "provider-v1",
        participants,
        "model-none",
        "prompt-none",
        resolution.capability_requirement_ids,
        resolution.method_requirements,
        resolution.configuration_ref_ids,
    )
    return compile_research_plan(definition, resolution, binding)


def _record(request, measurement_id: str, value: MeasurementValue, *, producer: str) -> MeasurementRecord:
    definition = request.measurement_protocol.definition(measurement_id)
    return MeasurementRecord(
        request.project_id,
        request.assignment.study_id,
        request.run_id,
        request.assignment.assignment_digest,
        request.assignment.variant_id,
        producer,
        "e" * 64,
        measurement_id,
        definition.schema_id,
        definition.semantic_contract_digest,
        request.measurement_protocol.semantic_digest,
        value,
        "t0",
        request.intervention,
        request.revision,
    )


class AgentProvider:
    protocol_identity = ExperimentTrialProtocolIdentity("trial.agent", AGENT_CFG)

    def run_trial(self, request):
        return _receipt(request, "agent", 1.0)


class OfflineProvider:
    protocol_identity = ExperimentTrialProtocolIdentity("trial.offline", OFFLINE_CFG)

    def run_trial(self, request):
        assert request.participant_schedule.applicable is False
        assert request.revision.applicable is False
        return _receipt(request, "offline", 0.5)


class CustomProvider:
    protocol_identity = ExperimentTrialProtocolIdentity("trial.custom", CUSTOM_CFG)

    def run_trial(self, request):
        return _receipt(request, "custom", 0.75)


def _receipt(request, label: str, score: float) -> TrialExecutionReceipt:
    records = (
        _record(request, "score", MeasurementValue(MeasurementValueKind.SCALAR, scalar=score), producer=label),
        _record(request, "trace", MeasurementValue(MeasurementValueKind.STRUCTURED, structured={"loop": label}), producer=label),
    )
    evidence = ArtifactReference(
        f"evidence-{label}",
        ScopeIdentity(ScopeKind.RUN, request.run_id),
        f"artifact-{label}",
        1,
    )
    return TrialExecutionReceipt(
        request.request_digest,
        request.assignment.assignment_digest,
        records,
        (evidence,),
    )


@pytest.mark.parametrize(
    ("provider", "participants", "revision"),
    (
        (AgentProvider(), (_participant("method", "method"),), ResearchRevision("r", "c" * 64)),
        (OfflineProvider(), (), None),
        (
            CustomProvider(),
            (
                _participant("actor", "actor"),
                _participant("judge", "evaluator", depends_on_roles=("actor",)),
            ),
            ResearchRevision("r", "d" * 64),
        ),
    ),
)
def test_structurally_distinct_trials_share_one_neutral_lifecycle(provider, participants, revision) -> None:
    plan = _plan(provider.protocol_identity, participants, revision)
    report = TrialMatrixExecutor().execute(plan, run_id="run-1", provider=provider)
    assert len(report.trial_receipt_digests) == len(plan.experiment_plan.assignments)
    assert len(report.records) == len(plan.experiment_plan.assignments) * 2
    assert {row.measurement_id for row in report.records} == {"score", "trace"}


def test_trial_executor_rejects_provider_protocol_drift() -> None:
    plan = _plan(AgentProvider.protocol_identity, (), None)
    with pytest.raises(ValueError, match="protocol identity"):
        TrialMatrixExecutor().execute(plan, run_id="run-1", provider=OfflineProvider())


class LooseEvidenceProvider:
    protocol_identity = ExperimentTrialProtocolIdentity("trial.loose", "4" * 64)

    def run_trial(self, request):
        record = _record(
            request, "score",
            MeasurementValue(MeasurementValueKind.SCALAR, scalar=0.5),
            producer="loose",
        )
        trace = _record(
            request, "trace",
            MeasurementValue(MeasurementValueKind.STRUCTURED, structured={"loop": "loose"}),
            producer="loose",
        )
        return TrialExecutionReceipt(
            request.request_digest,
            request.assignment.assignment_digest,
            (record, trace),
            ("evidence:loose",),
        )


def test_trial_receipt_rejects_loose_string_evidence() -> None:
    plan = _plan(LooseEvidenceProvider.protocol_identity, (), None)
    with pytest.raises(TypeError, match="ArtifactReference"):
        TrialMatrixExecutor().execute(plan, run_id="run-1", provider=LooseEvidenceProvider())