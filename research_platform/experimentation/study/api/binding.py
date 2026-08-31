"""Author requirements and resolved producer-binding contributions for research compilation."""

from __future__ import annotations

from dataclasses import dataclass, field

from research_platform.experimentation.experiment.api import ExperimentParticipantSpec
from research_platform.platform.kernel import canonical_digest, require_sha256


def _text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _sha(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    return require_sha256(value, field_name)

def _unique_strings(value: object, field_name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field_name} must be a tuple")
    if any(type(row) is not str or not row.strip() for row in value):
        raise TypeError(f"{field_name} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field_name} must be unique")
    return value


@dataclass(frozen=True, slots=True)
class ResearchParticipantRequirement:
    role: str
    participant_kind: str
    method_id: str
    treatment_id: str
    capability_requirement_ids: tuple[str, ...] = ()
    configuration_ref_ids: tuple[str, ...] = ()
    depends_on_roles: tuple[str, ...] = ()
    requirement_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.role, "participant requirement role")
        _text(self.participant_kind, "participant requirement participant_kind")
        _text(self.method_id, "participant requirement method_id")
        _text(self.treatment_id, "participant requirement treatment_id")
        _unique_strings(self.capability_requirement_ids, "participant capability requirements")
        _unique_strings(self.configuration_ref_ids, "participant configuration refs")
        _unique_strings(self.depends_on_roles, "participant dependency roles")
        if self.role in self.depends_on_roles:
            raise ValueError("participant requirement cannot depend on itself")
        object.__setattr__(self, "requirement_digest", canonical_digest({
            "role": self.role,
            "participant_kind": self.participant_kind,
            "method_id": self.method_id,
            "treatment_id": self.treatment_id,
            "capability_requirement_ids": self.capability_requirement_ids,
            "configuration_ref_ids": self.configuration_ref_ids,
            "depends_on_roles": self.depends_on_roles,
        }))


@dataclass(frozen=True, slots=True)
class ResearchBindingRequirements:
    trial_provider_requirement_id: str
    participants: tuple[ResearchParticipantRequirement, ...] = ()
    model_requirement_id: str | None = None
    prompt_configuration_id: str | None = None
    requirements_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.trial_provider_requirement_id, "trial provider requirement id")
        if self.model_requirement_id is not None:
            _text(self.model_requirement_id, "model requirement id")
        if self.prompt_configuration_id is not None:
            _text(self.prompt_configuration_id, "prompt configuration id")
        if type(self.participants) is not tuple or any(
            type(row) is not ResearchParticipantRequirement for row in self.participants
        ):
            raise TypeError("binding requirements participants must be ResearchParticipantRequirement")
        roles = tuple(row.role for row in self.participants)
        if len(roles) != len(set(roles)):
            raise ValueError("binding requirement participant roles must be unique")
        known = set(roles)
        if any(dep not in known for row in self.participants for dep in row.depends_on_roles):
            raise ValueError("binding requirement participant dependency is undeclared")
        object.__setattr__(self, "requirements_digest", canonical_digest({
            "trial_provider_requirement_id": self.trial_provider_requirement_id,
            "participants": tuple(row.requirement_digest for row in self.participants),
            "model_requirement_id": self.model_requirement_id,
            "prompt_configuration_id": self.prompt_configuration_id,
        }))


@dataclass(frozen=True, slots=True)
class ResearchRequirementResolution:
    project_manifest_digest: str
    requirements_digest: str
    capability_requirement_ids: tuple[str, ...]
    method_requirements: tuple[tuple[str, str], ...]
    configuration_ref_ids: tuple[str, ...]
    resolution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.project_manifest_digest, "requirement resolution project_manifest_digest")
        _sha(self.requirements_digest, "requirement resolution requirements_digest")
        _unique_strings(self.capability_requirement_ids, "resolved capability requirements")
        if type(self.method_requirements) is not tuple or any(type(row) is not tuple or len(row) != 2 or any(type(item) is not str or not item.strip() for item in row) for row in self.method_requirements):
            raise TypeError("resolved method requirements must be non-empty string pairs")
        if len(self.method_requirements) != len(set(self.method_requirements)):
            raise ValueError("resolved method requirements must be unique")
        _unique_strings(self.configuration_ref_ids, "resolved configuration refs")
        object.__setattr__(self, "resolution_digest", canonical_digest({
            "project_manifest_digest": self.project_manifest_digest,
            "requirements_digest": self.requirements_digest,
            "capability_requirement_ids": self.capability_requirement_ids,
            "method_requirements": self.method_requirements,
            "configuration_ref_ids": self.configuration_ref_ids,
        }))


@dataclass(frozen=True, slots=True)
class ResearchBindingContribution:
    requirement_resolution_digest: str
    provider_id: str
    participants: tuple[ExperimentParticipantSpec, ...]
    model_stack_digest: str
    prompt_generation: str
    satisfied_capability_requirement_ids: tuple[str, ...]
    satisfied_method_requirements: tuple[tuple[str, str], ...]
    satisfied_configuration_ref_ids: tuple[str, ...]
    contribution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.requirement_resolution_digest, "binding contribution resolution digest")
        _text(self.provider_id, "binding contribution provider_id")
        _sha(self.model_stack_digest, "binding contribution model_stack_digest")
        _text(self.prompt_generation, "binding contribution prompt_generation")
        if type(self.participants) is not tuple or any(
            type(row) is not ExperimentParticipantSpec for row in self.participants
        ):
            raise TypeError("binding contribution participants must be ExperimentParticipantSpec")
        roles = tuple(row.role for row in self.participants)
        if len(roles) != len(set(roles)):
            raise ValueError("binding contribution participant roles must be unique")
        _unique_strings(self.satisfied_capability_requirement_ids, "satisfied capability requirements")
        if type(self.satisfied_method_requirements) is not tuple or any(type(row) is not tuple or len(row) != 2 or any(type(item) is not str or not item.strip() for item in row) for row in self.satisfied_method_requirements):
            raise TypeError("satisfied method requirements must be non-empty string pairs")
        if len(self.satisfied_method_requirements) != len(set(self.satisfied_method_requirements)):
            raise ValueError("satisfied method requirements must be unique")
        _unique_strings(self.satisfied_configuration_ref_ids, "satisfied configuration refs")
        object.__setattr__(self, "contribution_digest", canonical_digest({
            "requirement_resolution_digest": self.requirement_resolution_digest,
            "provider_id": self.provider_id,
            "participants": self.participants,
            "model_stack_digest": self.model_stack_digest,
            "prompt_generation": self.prompt_generation,
            "satisfied_capability_requirement_ids": self.satisfied_capability_requirement_ids,
            "satisfied_method_requirements": self.satisfied_method_requirements,
            "satisfied_configuration_ref_ids": self.satisfied_configuration_ref_ids,
        }))


__all__ = [
    "ResearchBindingContribution",
    "ResearchBindingRequirements",
    "ResearchParticipantRequirement",
    "ResearchRequirementResolution",
]
