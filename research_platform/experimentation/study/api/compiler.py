"""Side-effect-free compiler from author research facts to typed run facets."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Protocol

from research_platform.experimentation.experiment.api import (
    ExperimentParticipantTopology,
    ExperimentSpec,
    ExperimentTrialProtocolIdentity,
)
from research_platform.experimentation.identity import OptionalIdentityFacet, RunResearchSemanticsReference
from research_platform.platform.kernel import canonical_digest

from .binding import ResearchBindingContribution, ResearchRequirementResolution
from .contracts import StudyAssignment, StudyProtocol, StudyVariantSpec, VariantKind
from .design import (
    FactorSelection,
    ParticipantSchedule,
    ResearchStudyDefinition,
    StudyIntervention,
)
from .measurement import MeasurementProtocol, MeasurementValueKind
from .plan import ExperimentPlan, VariantBinding


class ProjectIdentityProjection(Protocol):
    project_id: str


class CapabilityRequirementProjection(Protocol):
    requirement_id: str


class MethodRequirementProjection(Protocol):
    method_id: str
    treatment_id: str


class ConfigurationReferenceProjection(Protocol):
    configuration_id: str


class ResearchProjectManifestProjection(Protocol):
    identity: ProjectIdentityProjection
    semantic_digest: str
    capability_requirements: tuple[CapabilityRequirementProjection, ...]
    method_requirements: tuple[MethodRequirementProjection, ...]
    configuration_refs: tuple[ConfigurationReferenceProjection, ...]


def _unique_preserving_order(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def resolve_research_requirements(
    definition: ResearchStudyDefinition,
    project_manifest: ResearchProjectManifestProjection,
) -> ResearchRequirementResolution:
    """Algorithm-Complexity: O(N)
    Algorithm-Rationale: N is total declared and available capability, method and configuration requirements; each row is indexed or filtered a constant number of times.
    """
    if type(definition) is not ResearchStudyDefinition:
        raise TypeError("requirement resolver requires ResearchStudyDefinition")
    identity = getattr(project_manifest, "identity", None)
    if getattr(identity, "project_id", None) != definition.project_id:
        raise ValueError("research requirements belong to a different project")
    project_digest = getattr(project_manifest, "semantic_digest", None)
    if type(project_digest) is not str or len(project_digest) != 64 or any(ch not in "0123456789abcdef" for ch in project_digest):
        raise TypeError("project manifest semantic_digest must be lowercase SHA-256")
    available_capabilities = {row.requirement_id for row in project_manifest.capability_requirements}
    available_methods = {(row.method_id, row.treatment_id) for row in project_manifest.method_requirements}
    available_configs = {row.configuration_id for row in project_manifest.configuration_refs}
    requirements = definition.binding_requirements
    capability_ids = [requirements.trial_provider_requirement_id]
    if requirements.model_requirement_id is not None:
        capability_ids.append(requirements.model_requirement_id)
    method_pairs = []
    configuration_ids = []
    if requirements.prompt_configuration_id is not None:
        configuration_ids.append(requirements.prompt_configuration_id)
    for participant in requirements.participants:
        capability_ids.extend(participant.capability_requirement_ids)
        method_pairs.append((participant.method_id, participant.treatment_id))
        configuration_ids.extend(participant.configuration_ref_ids)
    selected_capabilities = _unique_preserving_order(capability_ids)
    selected_methods = _unique_preserving_order(method_pairs)
    selected_configs = _unique_preserving_order(configuration_ids)
    missing_capabilities = tuple(row for row in selected_capabilities if row not in available_capabilities)
    missing_methods = tuple(row for row in selected_methods if row not in available_methods)
    missing_configs = tuple(row for row in selected_configs if row not in available_configs)
    if missing_capabilities or missing_methods or missing_configs:
        raise ValueError(f"research requirements unresolved: capabilities={missing_capabilities} methods={missing_methods} configurations={missing_configs}")
    return ResearchRequirementResolution(
        project_digest, definition.binding_requirement_digest,
        selected_capabilities, selected_methods, selected_configs,
    )


@dataclass(frozen=True, slots=True)
class ResearchPlanDiff:
    changed_facets: tuple[str, ...]
    scientific_design_changed: bool
    binding_changed: bool
    execution_plan_changed: bool
    measurement_semantics_changed: bool
    checkpoint_compatible: bool
    exact_plan_changed: bool
    diff_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.changed_facets) is not tuple:
            raise TypeError("research plan diff changed_facets must be a tuple")
        if len(self.changed_facets) != len(set(self.changed_facets)):
            raise ValueError("research plan diff changed_facets must be unique")
        object.__setattr__(self, "diff_digest", canonical_digest({
            "changed_facets": self.changed_facets,
            "scientific_design_changed": self.scientific_design_changed,
            "binding_changed": self.binding_changed,
            "execution_plan_changed": self.execution_plan_changed,
            "measurement_semantics_changed": self.measurement_semantics_changed,
            "checkpoint_compatible": self.checkpoint_compatible,
            "exact_plan_changed": self.exact_plan_changed,
        }))


@dataclass(frozen=True, slots=True)
class CompiledResearchPlan:
    definition_digest: str
    scientific_design_digest: str
    participant_design_digest: str
    binding_requirement_digest: str
    requirement_resolution_digest: str
    binding_digest: str
    execution_policy_digest: str
    benchmark_cut_digest: str
    interventions: tuple[StudyIntervention, ...]
    protocol: StudyProtocol
    experiment_plan: ExperimentPlan
    experiment: ExperimentSpec
    measurement_protocol: MeasurementProtocol
    participant_schedule: ParticipantSchedule | None
    trial_protocol_identity: ExperimentTrialProtocolIdentity
    research_plan_digest: str
    research_semantics: RunResearchSemanticsReference

    def __post_init__(self) -> None:
        expected = canonical_digest({
            "definition_digest": self.definition_digest,
            "scientific_design_digest": self.scientific_design_digest,
            "participant_design_digest": self.participant_design_digest,
            "binding_requirement_digest": self.binding_requirement_digest,
            "requirement_resolution_digest": self.requirement_resolution_digest,
            "binding_digest": self.binding_digest,
            "execution_policy_digest": self.execution_policy_digest,
            "benchmark_cut_digest": self.benchmark_cut_digest,
            "interventions": tuple(row.intervention_digest for row in self.interventions),
            "study_plan_digest": self.experiment_plan.plan_digest,
            "experiment_digest": self.experiment.identity_digest(),
            "measurement_semantics_digest": self.measurement_protocol.semantic_digest,
        })
        if expected != self.research_plan_digest:
            raise ValueError("compiled research plan digest is not authoritative")
        if self.research_semantics.research_plan_digest != self.research_plan_digest:
            raise ValueError("compiled research semantics do not bind the research plan")


def _factor_selections(
    definition: ResearchStudyDefinition,
) -> tuple[tuple[FactorSelection, ...], ...]:
    if not definition.factors:
        return ((),)
    return tuple(
        tuple(
            FactorSelection(factor.factor_id, level.level_id, level.level_digest)
            for factor, level in zip(definition.factors, levels, strict=True)
        )
        for levels in product(*(factor.levels for factor in definition.factors))
    )


def _intervention_for(
    definition: ResearchStudyDefinition,
    selections: tuple[FactorSelection, ...],
) -> StudyIntervention:
    control = True
    for factor, selected in zip(definition.factors, selections, strict=True):
        level = next(row for row in factor.levels if row.level_id == selected.level_id)
        if not level.control:
            control = False
            break
    selection_digest = canonical_digest(selections)
    intervention_id = "control" if control else f"intervention-{selection_digest[:16]}"
    return StudyIntervention(intervention_id, selections)


def _variant_for(
    definition: ResearchStudyDefinition,
    intervention: StudyIntervention,
    binding: ResearchBindingContribution,
) -> StudyVariantSpec:
    return StudyVariantSpec(
        intervention.intervention_id,
        VariantKind.CONTROL if intervention.control else VariantKind.TREATMENT,
        binding.provider_id,
        intervention.intervention_digest,
        definition.trial_budget.budget_id,
    )


def _assignments(
    definition: ResearchStudyDefinition,
    variants: tuple[StudyVariantSpec, ...],
) -> tuple[StudyAssignment, ...]:
    """Expand each declared repetition/variant/seed/task exactly once."""
    tasks = definition.benchmark.selected_tasks(definition.benchmark_split_id)
    return tuple(
        StudyAssignment(
            definition.study_id,
            variant.variant_id,
            repetition,
            seed,
            task.task_id,
        )
        for repetition, variant, seed, task in product(
            range(definition.repetitions), variants, definition.seeds, tasks
        )
    )


def _scalar_measurement_names(protocol: MeasurementProtocol) -> tuple[str, ...]:
    return tuple(
        row.measurement_id
        for row in protocol.definitions
        if row.value_kind is MeasurementValueKind.SCALAR
    )


def _protocol(
    definition: ResearchStudyDefinition,
    variants: tuple[StudyVariantSpec, ...],
    assignments: tuple[StudyAssignment, ...],
) -> StudyProtocol:
    seed_schedule_digest = canonical_digest({
        "seeds": definition.seeds,
        "repetitions": definition.repetitions,
        "assignments": tuple(row.assignment_digest for row in assignments),
    })
    return StudyProtocol(
        definition.study_id,
        definition.workload_id,
        variants,
        definition.repetitions,
        seed_schedule_digest,
        _scalar_measurement_names(definition.measurement_protocol),
        definition.benchmark.cut_digest,
        (definition.trial_budget.budget_id,),
        definition.concurrency_policy,
    )


def _bindings(
    variants: tuple[StudyVariantSpec, ...],
    binding: ResearchBindingContribution,
) -> tuple[VariantBinding, ...]:
    return tuple(
        VariantBinding(
            variant,
            variant.configuration_digest,
            binding.provider_id,
            "none",
            variant.kind.value,
        )
        for variant in variants
    )


def _experiment(
    definition: ResearchStudyDefinition,
    protocol: StudyProtocol,
    binding: ResearchBindingContribution,
) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id=definition.experiment_id,
        study_id=definition.study_id,
        project_id=definition.project_id,
        participants=binding.participants,
        model_stack_digest=binding.model_stack_digest,
        prompt_generation=binding.prompt_generation,
        workload_digest=canonical_digest({
            "workload_id": definition.workload_id,
            "benchmark_cut_digest": definition.benchmark.cut_digest,
        }),
        seed_digest=protocol.seed_schedule_digest,
        repetitions=definition.repetitions,
        trial_protocol_id=definition.trial_protocol_identity.protocol_id,
        trial_protocol_configuration_digest=(
            definition.trial_protocol_identity.configuration_digest
        ),
    )


def _schedule(
    experiment: ExperimentSpec,
) -> tuple[ParticipantSchedule | None, OptionalIdentityFacet, OptionalIdentityFacet]:
    if not experiment.participants:
        absent = OptionalIdentityFacet()
        return None, absent, absent
    topology = ExperimentParticipantTopology.from_spec(experiment)
    waves = tuple(tuple(row.role for row in wave) for wave in topology.waves())
    schedule = ParticipantSchedule(waves)
    return (
        schedule,
        OptionalIdentityFacet(topology.digest()),
        OptionalIdentityFacet(schedule.schedule_digest),
    )


def _revision_facet(definition: ResearchStudyDefinition) -> OptionalIdentityFacet:
    if definition.revision is None:
        return OptionalIdentityFacet()
    return OptionalIdentityFacet(definition.revision.revision_digest)


def _validate_binding_contribution(
    definition: ResearchStudyDefinition,
    resolution: ResearchRequirementResolution,
    binding: ResearchBindingContribution,
) -> None:
    if type(resolution) is not ResearchRequirementResolution:
        raise TypeError("research compiler requires ResearchRequirementResolution")
    if type(binding) is not ResearchBindingContribution:
        raise TypeError("research compiler requires ResearchBindingContribution")
    if resolution.requirements_digest != definition.binding_requirement_digest:
        raise ValueError("requirement resolution does not bind the author definition")
    if binding.requirement_resolution_digest != resolution.resolution_digest:
        raise ValueError("binding contribution does not bind requirement resolution")
    if binding.satisfied_capability_requirement_ids != resolution.capability_requirement_ids:
        raise ValueError("binding contribution capability coverage drifted")
    if binding.satisfied_method_requirements != resolution.method_requirements:
        raise ValueError("binding contribution method coverage drifted")
    if binding.satisfied_configuration_ref_ids != resolution.configuration_ref_ids:
        raise ValueError("binding contribution configuration coverage drifted")
    requirements = definition.binding_requirements.participants
    if tuple(row.role for row in binding.participants) != tuple(row.role for row in requirements):
        raise ValueError("binding contribution participant roles drifted")
    for requirement, participant in zip(requirements, binding.participants, strict=True):
        if participant.implementation.kind != requirement.participant_kind:
            raise ValueError("binding contribution participant kind drifted")
        if participant.depends_on_roles != requirement.depends_on_roles:
            raise ValueError("binding contribution participant dependencies drifted")


def compile_research_plan(
    definition: ResearchStudyDefinition,
    resolution: ResearchRequirementResolution,
    binding: ResearchBindingContribution,
) -> CompiledResearchPlan:
    if type(definition) is not ResearchStudyDefinition:
        raise TypeError("research compiler requires ResearchStudyDefinition")
    _validate_binding_contribution(definition, resolution, binding)
    interventions = tuple(
        _intervention_for(definition, rows) for rows in _factor_selections(definition)
    )
    variants = tuple(_variant_for(definition, row, binding) for row in interventions)
    assignments = _assignments(definition, variants)
    protocol = _protocol(definition, variants, assignments)
    experiment_plan = ExperimentPlan.compile(
        protocol, _bindings(variants, binding), assignments
    )
    experiment = _experiment(definition, protocol, binding)
    participant_schedule, topology, schedule = _schedule(experiment)
    intervention = OptionalIdentityFacet(
        canonical_digest(tuple(row.intervention_digest for row in interventions))
    )
    revision = _revision_facet(definition)
    trial_protocol = definition.trial_protocol_identity
    provisional_plan_digest = canonical_digest({
        "definition_digest": definition.definition_digest,
        "scientific_design_digest": definition.scientific_design_digest,
        "participant_design_digest": definition.participant_design_digest,
        "binding_requirement_digest": definition.binding_requirement_digest,
        "requirement_resolution_digest": resolution.resolution_digest,
        "binding_digest": binding.contribution_digest,
        "execution_policy_digest": definition.execution_policy_digest,
        "benchmark_cut_digest": definition.benchmark.cut_digest,
        "interventions": tuple(row.intervention_digest for row in interventions),
        "study_plan_digest": experiment_plan.plan_digest,
        "experiment_digest": experiment.identity_digest(),
        "measurement_semantics_digest": definition.measurement_protocol.semantic_digest,
    })
    semantics = RunResearchSemanticsReference(
        research_plan_digest=provisional_plan_digest,
        study_plan_digest=experiment_plan.plan_digest,
        measurement_protocol_digest=definition.measurement_protocol.semantic_digest,
        trial_protocol_digest=trial_protocol.digest(),
        intervention=intervention,
        topology=topology,
        participant_schedule=schedule,
        revision=revision,
        replay_level=definition.replay_level,
    )
    return CompiledResearchPlan(
        definition_digest=definition.definition_digest,
        scientific_design_digest=definition.scientific_design_digest,
        participant_design_digest=definition.participant_design_digest,
        binding_requirement_digest=definition.binding_requirement_digest,
        requirement_resolution_digest=resolution.resolution_digest,
        binding_digest=binding.contribution_digest,
        execution_policy_digest=definition.execution_policy_digest,
        benchmark_cut_digest=definition.benchmark.cut_digest,
        interventions=interventions,
        protocol=protocol,
        experiment_plan=experiment_plan,
        experiment=experiment,
        measurement_protocol=definition.measurement_protocol,
        participant_schedule=participant_schedule,
        trial_protocol_identity=trial_protocol,
        research_plan_digest=provisional_plan_digest,
        research_semantics=semantics,
    )

def diff_research_plans(
    previous: CompiledResearchPlan,
    candidate: CompiledResearchPlan,
) -> ResearchPlanDiff:
    if type(previous) is not CompiledResearchPlan or type(candidate) is not CompiledResearchPlan:
        raise TypeError("research plan diff requires compiled plans")
    checks = (
        ("scientific_design", previous.scientific_design_digest, candidate.scientific_design_digest),
        ("participant_design", previous.participant_design_digest, candidate.participant_design_digest),
        ("provider_binding", previous.binding_digest, candidate.binding_digest),
        ("execution_policy", previous.execution_policy_digest, candidate.execution_policy_digest),
        ("benchmark_cut", previous.benchmark_cut_digest, candidate.benchmark_cut_digest),
        ("assignments", previous.experiment_plan.assignment_digest, candidate.experiment_plan.assignment_digest),
        ("variant_bindings", previous.experiment_plan.binding_digest, candidate.experiment_plan.binding_digest),
        ("measurement_semantics", previous.measurement_protocol.semantic_digest, candidate.measurement_protocol.semantic_digest),
        ("topology", previous.research_semantics.topology, candidate.research_semantics.topology),
        ("participant_schedule", previous.research_semantics.participant_schedule, candidate.research_semantics.participant_schedule),
        ("revision", previous.research_semantics.revision, candidate.research_semantics.revision),
        ("replay_level", previous.research_semantics.replay_level, candidate.research_semantics.replay_level),
    )
    changed = tuple(name for name, left, right in checks if left != right)
    checkpoint_compatible = (
        previous.research_semantics.checkpoint_compatibility_digest
        == candidate.research_semantics.checkpoint_compatibility_digest
        and previous.benchmark_cut_digest == candidate.benchmark_cut_digest
        and previous.experiment_plan.assignment_digest
        == candidate.experiment_plan.assignment_digest
    )
    return ResearchPlanDiff(
        changed_facets=changed,
        scientific_design_changed=(
            previous.scientific_design_digest != candidate.scientific_design_digest
        ),
        binding_changed=(previous.binding_digest != candidate.binding_digest),
        execution_plan_changed=(
            previous.execution_policy_digest != candidate.execution_policy_digest
            or previous.research_semantics.topology != candidate.research_semantics.topology
            or previous.research_semantics.participant_schedule
            != candidate.research_semantics.participant_schedule
        ),
        measurement_semantics_changed=(
            previous.measurement_protocol.semantic_digest
            != candidate.measurement_protocol.semantic_digest
        ),
        checkpoint_compatible=checkpoint_compatible,
        exact_plan_changed=(previous.research_plan_digest != candidate.research_plan_digest),
    )


__all__ = [
    "CompiledResearchPlan",
    "ResearchPlanDiff",
    "ResearchProjectManifestProjection",
    "compile_research_plan",
    "resolve_research_requirements",
    "diff_research_plans",
]
