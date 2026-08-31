from __future__ import annotations

from dataclasses import dataclass, replace

from research_platform.experimentation.api import (
    ResearchBindingContribution,
    ResearchBindingRequirements,
    ResearchParticipantRequirement,
    compile_research_plan,
    diff_research_plans,
    resolve_research_requirements,
)
from research_platform.experimentation.experiment.api import (
    ExperimentParticipantSpec,
    ExperimentTrialProtocolIdentity,
)
from research_platform.experimentation.study.api import (
    BenchmarkTaskSet, FactorLevelSpec, MeasurementDefinition,
    MeasurementProtocol, MeasurementValueKind, ResearchRevision,
    ResearchStudyDefinition, StudyFactorSpec, TaskDefinition, TrialBudget,
)
from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity, ParticipantSessionRuntimeIdentity,
)


@dataclass(frozen=True)
class _ProjectIdentity:
    project_id: str


@dataclass(frozen=True)
class _CapabilityRequirement:
    requirement_id: str


@dataclass(frozen=True)
class _MethodRequirement:
    method_id: str
    treatment_id: str


@dataclass(frozen=True)
class _ConfigurationReference:
    configuration_id: str


@dataclass(frozen=True)
class _ProjectManifest:
    identity: _ProjectIdentity
    semantic_digest: str
    capability_requirements: tuple[_CapabilityRequirement, ...]
    method_requirements: tuple[_MethodRequirement, ...]
    configuration_refs: tuple[_ConfigurationReference, ...]


CFG = "c" * 64


def _participant(role: str, kind: str, *, depends_on_roles: tuple[str, ...] = ()) -> ExperimentParticipantSpec:
    return ExperimentParticipantSpec(
        role=role,
        implementation=ParticipantImplementationIdentity(kind, f"{kind}-impl", "1", "1", "1", "a" * 64),
        runtime=ParticipantSessionRuntimeIdentity(f"runtime.{kind}", "1", "1", "b" * 64),
        configuration_digest="d" * 64,
        depends_on_roles=depends_on_roles,
    )


def _benchmark(tag: str = "a") -> BenchmarkTaskSet:
    task = TaskDefinition("task-1", "1", "generic", "task.v1", tag * 64)
    return BenchmarkTaskSet("benchmark", "1", "b" * 64, "task.v1", (task,))


def _measurements(schema: str = "trace-v1") -> MeasurementProtocol:
    return MeasurementProtocol(
        "measurements-v2",
        (
            MeasurementDefinition("score", "scalar-v1", MeasurementValueKind.SCALAR),
            MeasurementDefinition("trace", schema, MeasurementValueKind.STRUCTURED),
        ),
    )


def _binding_requirements() -> ResearchBindingRequirements:
    return ResearchBindingRequirements(
        "trial-provider",
        participants=(
            ResearchParticipantRequirement("actor", "actor", "method", "actor"),
            ResearchParticipantRequirement("evaluator", "evaluator", "method", "evaluator", depends_on_roles=("actor",)),
            ResearchParticipantRequirement("critic", "critic", "method", "critic", depends_on_roles=("evaluator",)),
        ),
        model_requirement_id="model",
        prompt_configuration_id="prompt-config",
    )


def _manifest() -> _ProjectManifest:
    return _ProjectManifest(
        _ProjectIdentity("project-1"),
        "9" * 64,
        (_CapabilityRequirement("trial-provider"), _CapabilityRequirement("model")),
        (
            _MethodRequirement("method", "actor"),
            _MethodRequirement("method", "evaluator"),
            _MethodRequirement("method", "critic"),
        ),
        (_ConfigurationReference("prompt-config"),),
    )


def _definition(
    *,
    measurements: MeasurementProtocol | None = None,
    seeds: tuple[str, ...] = ("seed-a", "seed-b"),
    benchmark: BenchmarkTaskSet | None = None,
    budget: TrialBudget | None = None,
) -> ResearchStudyDefinition:
    factors = (
        StudyFactorSpec(
            "memory",
            (
                FactorLevelSpec("off", False, control=True),
                FactorLevelSpec("on", True),
            ),
        ),
        StudyFactorSpec(
            "model",
            (
                FactorLevelSpec("base", "base", control=True),
                FactorLevelSpec("enhanced", "enhanced"),
            ),
        ),
    )
    return ResearchStudyDefinition(
        "project-1", "experiment-1", "study-1", "workload-1",
        factors, seeds, 2, measurements or _measurements(),
        benchmark or _benchmark(), None, _binding_requirements(),
        ExperimentTrialProtocolIdentity("trial.agent", CFG),
        ResearchRevision("revision-1", "d" * 64),
        trial_budget=budget or TrialBudget("standard", max_steps=12, max_seconds=180.0),
    )


def _compile(definition: ResearchStudyDefinition, *, provider_id: str = "provider-v1"):
    manifest = _manifest()
    resolution = resolve_research_requirements(definition, manifest)
    participants = (
        _participant("actor", "actor"),
        _participant("evaluator", "evaluator", depends_on_roles=("actor",)),
        _participant("critic", "critic", depends_on_roles=("evaluator",)),
    )
    binding = ResearchBindingContribution(
        resolution.resolution_digest,
        provider_id,
        participants,
        "model-stack-v1",
        "prompt-v1",
        resolution.capability_requirement_ids,
        resolution.method_requirements,
        resolution.configuration_ref_ids,
    )
    return compile_research_plan(definition, resolution, binding)


def test_compiler_expands_factor_seed_repetition_task_matrix_and_schedule() -> None:
    plan = _compile(_definition())
    assert len(plan.interventions) == 4
    assert sum(row.control for row in plan.interventions) == 1
    assert len(plan.experiment_plan.assignments) == 16
    assert {row.seed for row in plan.experiment_plan.assignments} == {"seed-a", "seed-b"}
    assert {row.task_id for row in plan.experiment_plan.assignments} == {"task-1"}
    assert plan.protocol.metric_names == ("score",)
    assert plan.participant_schedule.waves == (("actor",), ("evaluator",), ("critic",))
    assert plan.research_semantics.study_plan_digest == plan.experiment_plan.plan_digest
    assert plan.research_semantics.measurement_protocol_digest == plan.measurement_protocol.semantic_digest
    assert plan.research_semantics.participant_schedule.applicable is True
    assert plan.trial_protocol_identity == ExperimentTrialProtocolIdentity("trial.agent", CFG)


def test_compiler_accepts_non_scalar_measurements_without_fake_numeric_metric() -> None:
    measurements = MeasurementProtocol(
        "structured-only",
        (MeasurementDefinition("trajectory", "trajectory-v1", MeasurementValueKind.SEQUENCE),),
    )
    plan = _compile(_definition(measurements=measurements))
    assert plan.protocol.metric_names == ()
    assert len(plan.experiment_plan.assignments) == 16


def test_facet_diff_separates_measurement_seed_and_budget_changes() -> None:
    base = _compile(_definition())
    measurement = _compile(_definition(measurements=_measurements("trace-v2")))
    measurement_diff = diff_research_plans(base, measurement)
    assert "measurement_semantics" in measurement_diff.changed_facets
    assert measurement_diff.scientific_design_changed is True
    assert measurement_diff.measurement_semantics_changed is True
    assert measurement_diff.checkpoint_compatible is True

    seed = _compile(_definition(seeds=("seed-a", "seed-c")))
    seed_diff = diff_research_plans(base, seed)
    assert "assignments" in seed_diff.changed_facets
    assert seed_diff.scientific_design_changed is True
    assert seed_diff.checkpoint_compatible is False

    budget = _compile(
        _definition(budget=TrialBudget("standard", max_steps=24, max_seconds=180.0))
    )
    budget_diff = diff_research_plans(base, budget)
    assert budget_diff.scientific_design_changed is False
    assert budget_diff.execution_plan_changed is True
    assert "execution_policy" in budget_diff.changed_facets


def test_provider_replacement_changes_binding_not_scientific_design() -> None:
    definition = _definition()
    left = _compile(definition, provider_id="provider-v1")
    right = _compile(definition, provider_id="provider-v2")
    diff = diff_research_plans(left, right)
    assert left.scientific_design_digest == right.scientific_design_digest
    assert left.participant_design_digest == right.participant_design_digest
    assert left.binding_requirement_digest == right.binding_requirement_digest
    assert left.binding_digest != right.binding_digest
    assert diff.scientific_design_changed is False
    assert diff.binding_changed is True
    assert "provider_binding" in diff.changed_facets


def test_requirement_resolution_and_binding_drift_fail_closed() -> None:
    definition = _definition()
    resolution = resolve_research_requirements(definition, _manifest())
    participants = (
        _participant("actor", "actor"),
        _participant("evaluator", "evaluator", depends_on_roles=("actor",)),
        _participant("critic", "critic", depends_on_roles=("evaluator",)),
    )
    binding = ResearchBindingContribution(
        resolution.resolution_digest, "provider-v1", participants,
        "model-stack-v1", "prompt-v1",
        resolution.capability_requirement_ids,
        resolution.method_requirements,
        resolution.configuration_ref_ids,
    )
    bad = replace(binding, provider_id="provider-v2")
    assert bad.contribution_digest != binding.contribution_digest
    bad_participants = (
        _participant("actor", "wrongkind"), participants[1], participants[2],
    )
    bad_binding = replace(binding, participants=bad_participants)
    import pytest
    with pytest.raises(ValueError, match="participant kind"):
        compile_research_plan(definition, resolution, bad_binding)


def test_compiler_is_deterministic_for_identical_author_definition_and_binding() -> None:
    definition = _definition()
    left = _compile(definition)
    right = _compile(definition)
    assert left.research_plan_digest == right.research_plan_digest
    assert left.experiment_plan.plan_digest == right.experiment_plan.plan_digest
    assert left.research_semantics == right.research_semantics
