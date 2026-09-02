"""Author requirements and proof-backed producer bindings for research compilation."""

from __future__ import annotations

from dataclasses import dataclass, field

from noetrium_platform.foundation.governance.architecture.api import BindingProof, CompositionSubject
from noetrium_platform.capabilities.model.api.project import ProjectModelBinding
from noetrium_platform.capabilities.participant.api.project import ProjectParticipantBinding
from noetrium_platform.foundation.kernel.kernel import canonical_digest, require_sha256
from noetrium_platform.foundation.portfolio.api import (
    ProjectCapabilityRequirement,
    ProjectConfigurationReference,
    ProjectMethodRequirement,
    ProjectProviderBinding,
)


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
            if self.model_requirement_id is None:
                raise ValueError("prompt configuration requires a model requirement")
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
    project_subject: CompositionSubject
    requirements_digest: str
    capability_requirements: tuple[ProjectCapabilityRequirement, ...]
    method_requirements: tuple[ProjectMethodRequirement, ...]
    configuration_refs: tuple[ProjectConfigurationReference, ...]
    provider_bindings: tuple[ProjectProviderBinding, ...]

    resolution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.project_manifest_digest, "requirement resolution project_manifest_digest")
        if not isinstance(self.project_subject, CompositionSubject):
            raise TypeError("requirement resolution project_subject must be CompositionSubject")
        _sha(self.requirements_digest, "requirement resolution requirements_digest")
        if type(self.capability_requirements) is not tuple or any(
            not isinstance(row, ProjectCapabilityRequirement) for row in self.capability_requirements
        ):
            raise TypeError("resolved capability requirements must be ProjectCapabilityRequirement")
        if type(self.method_requirements) is not tuple or any(
            not isinstance(row, ProjectMethodRequirement) for row in self.method_requirements
        ):
            raise TypeError("resolved method requirements must be ProjectMethodRequirement")
        if type(self.configuration_refs) is not tuple or any(
            not isinstance(row, ProjectConfigurationReference) for row in self.configuration_refs
        ):
            raise TypeError("resolved configuration refs must be ProjectConfigurationReference")
        if type(self.provider_bindings) is not tuple or any(
            not isinstance(row, ProjectProviderBinding) for row in self.provider_bindings
        ):
            raise TypeError("resolved provider bindings must be ProjectProviderBinding")
        capability_ids = tuple(row.requirement_id for row in self.capability_requirements)
        method_keys = tuple((row.method_id, row.treatment_id) for row in self.method_requirements)
        config_ids = tuple(row.configuration_id for row in self.configuration_refs)
        if len(capability_ids) != len(set(capability_ids)) or len(method_keys) != len(set(method_keys)) or len(config_ids) != len(set(config_ids)):
            raise ValueError("requirement resolution contains duplicate requirement identities")

        if any(row.requirement_id not in set(capability_ids) for row in self.provider_bindings):
            raise ValueError("resolved provider binding names an unselected capability requirement")
        object.__setattr__(self, "resolution_digest", canonical_digest({
            "project_manifest_digest": self.project_manifest_digest,
            "project_subject": self.project_subject.key,
            "requirements_digest": self.requirements_digest,
            "capability_requirements": self.capability_requirements,
            "method_requirements": self.method_requirements,
            "configuration_refs": self.configuration_refs,
            "provider_bindings": self.provider_bindings,
        }))

    @property
    def capability_requirement_ids(self) -> tuple[str, ...]:
        return tuple(row.requirement_id for row in self.capability_requirements)

    @property
    def method_requirement_keys(self) -> tuple[tuple[str, str], ...]:
        return tuple((row.method_id, row.treatment_id) for row in self.method_requirements)

    @property
    def configuration_ref_ids(self) -> tuple[str, ...]:
        return tuple(row.configuration_id for row in self.configuration_refs)

    def capability_requirement(self, requirement_id: str) -> ProjectCapabilityRequirement:
        matches = tuple(row for row in self.capability_requirements if row.requirement_id == requirement_id)
        if len(matches) != 1:
            raise KeyError(f"resolved capability requirement is not unique: {requirement_id}")
        return matches[0]


    def provider_bindings_for(self, requirement_id: str) -> tuple[ProjectProviderBinding, ...]:
        return tuple(row for row in self.provider_bindings if row.requirement_id == requirement_id)


@dataclass(frozen=True, slots=True)
class ResearchCapabilityBinding:
    requirement_id: str
    proof: BindingProof
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.requirement_id, "capability binding requirement_id")
        if not isinstance(self.proof, BindingProof):
            raise TypeError("capability binding proof must be BindingProof")
        object.__setattr__(self, "binding_digest", canonical_digest({
            "requirement_id": self.requirement_id,
            "proof_digest": self.proof.digest,
        }))


@dataclass(frozen=True, slots=True)
class ResearchParticipantBinding:
    role: str
    binding: ProjectParticipantBinding
    proof: BindingProof
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.role, "participant binding role")
        if not isinstance(self.binding, ProjectParticipantBinding):
            raise TypeError("participant binding must be ProjectParticipantBinding")
        if not isinstance(self.proof, BindingProof):
            raise TypeError("participant binding proof must be BindingProof")

        if self.binding.binding.role != self.role:
            raise ValueError("participant binding role drifted")
        if self.proof.requirement_digest.value != self.binding.requirement_digest:
            raise ValueError("participant binding proof requirement drifted")
        if self.proof.provider_identity != self.binding.provider_id:
            raise ValueError("participant binding proof provider drifted")
        if self.proof.provider_profile_digest.value != self.binding.provider_profile_digest:
            raise ValueError("participant binding proof profile drifted")
        expected_generation = f"participant-{self.binding.binding.runtime.digest()}"
        if self.proof.binding_generation != expected_generation:
            raise ValueError("participant binding proof generation drifted")
        object.__setattr__(self, "binding_digest", canonical_digest({
            "role": self.role,
            "domain_binding_digest": self.binding.digest(),
            "proof_digest": self.proof.digest,
        }))


@dataclass(frozen=True, slots=True)
class ResearchModelBinding:
    requirement_id: str
    binding: ProjectModelBinding
    proof: BindingProof
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.requirement_id, "model binding requirement_id")
        if not isinstance(self.binding, ProjectModelBinding):
            raise TypeError("model binding must be ProjectModelBinding")
        if not isinstance(self.proof, BindingProof):
            raise TypeError("model binding proof must be BindingProof")

        if self.proof.requirement_digest.value != self.binding.requirement_digest:
            raise ValueError("model binding proof requirement drifted")
        if self.proof.provider_identity != self.binding.provider_id:
            raise ValueError("model binding proof provider drifted")
        if self.proof.provider_profile_digest.value != self.binding.provider_profile_digest:
            raise ValueError("model binding proof profile drifted")
        expected_generation = f"model-{self.binding.deployment_generation}"
        if self.proof.binding_generation != expected_generation:
            raise ValueError("model binding proof generation drifted")
        object.__setattr__(self, "binding_digest", canonical_digest({
            "requirement_id": self.requirement_id,
            "domain_binding_digest": self.binding.digest(),
            "proof_digest": self.proof.digest,
        }))


@dataclass(frozen=True, slots=True)
class ResearchBindingContribution:
    requirement_resolution_digest: str
    capability_bindings: tuple[ResearchCapabilityBinding, ...]
    participant_bindings: tuple[ResearchParticipantBinding, ...] = ()
    model_binding: ResearchModelBinding | None = None
    contribution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.requirement_resolution_digest, "binding contribution resolution digest")
        if type(self.capability_bindings) is not tuple or any(
            not isinstance(row, ResearchCapabilityBinding) for row in self.capability_bindings
        ):
            raise TypeError("binding contribution capability_bindings must be typed")
        capability_digests = tuple(row.binding_digest for row in self.capability_bindings)
        if len(capability_digests) != len(set(capability_digests)):
            raise ValueError("binding contribution capability proofs must be unique")
        if type(self.participant_bindings) is not tuple or any(
            not isinstance(row, ResearchParticipantBinding) for row in self.participant_bindings
        ):
            raise TypeError("binding contribution participant_bindings must be typed")
        roles = tuple(row.role for row in self.participant_bindings)
        if len(roles) != len(set(roles)):
            raise ValueError("binding contribution participant roles must be unique")
        if self.model_binding is not None and not isinstance(self.model_binding, ResearchModelBinding):
            raise TypeError("binding contribution model_binding must be ResearchModelBinding or None")
        object.__setattr__(self, "contribution_digest", canonical_digest({
            "requirement_resolution_digest": self.requirement_resolution_digest,
            "capability_bindings": tuple(row.binding_digest for row in self.capability_bindings),
            "participant_bindings": tuple(row.binding_digest for row in self.participant_bindings),
            "model_binding": self.model_binding.binding_digest if self.model_binding is not None else None,
        }))

    def capability_bindings_for(self, requirement_id: str) -> tuple[ResearchCapabilityBinding, ...]:
        return tuple(row for row in self.capability_bindings if row.requirement_id == requirement_id)

    def capability_binding(self, requirement_id: str) -> ResearchCapabilityBinding:
        matches = self.capability_bindings_for(requirement_id)
        if len(matches) != 1:
            raise KeyError(f"binding contribution has no unique capability proof for {requirement_id}")
        return matches[0]


__all__ = [
    "ResearchBindingContribution",
    "ResearchBindingRequirements",
    "ResearchCapabilityBinding",
    "ResearchModelBinding",
    "ResearchParticipantBinding",
    "ResearchParticipantRequirement",
    "ResearchRequirementResolution",
]
