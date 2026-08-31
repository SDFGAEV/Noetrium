from __future__ import annotations

from dataclasses import dataclass
import re

from research_platform.platform.kernel import canonical_digest, require_sha256
from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity,
    ParticipantRuntimeBinding,
    ParticipantSessionRuntimeIdentity,
)
from research_platform.scope.api import ScopeIdentity, ScopeKind


@dataclass(frozen=True, slots=True)
class ExperimentParticipantSpec:
    role: str
    implementation: ParticipantImplementationIdentity
    runtime: ParticipantSessionRuntimeIdentity
    configuration_digest: str = ""
    depends_on_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValueError("participant role must be non-empty")
        if re.fullmatch(r"[a-z][a-z0-9_]*", self.implementation.kind) is None:
            raise ValueError("participant kind must be a safe operation namespace token")
        if re.fullmatch(r"[A-Za-z0-9_.:-]+", self.role) is None:
            raise ValueError("participant role must be a safe topology token")
        if self.role in self.depends_on_roles:
            raise ValueError(f"participant {self.role} cannot depend on itself")

    def runtime_binding(self) -> ParticipantRuntimeBinding:
        return ParticipantRuntimeBinding(
            self.role,
            self.implementation,
            self.runtime,
            self.configuration_digest,
        )


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    experiment_id: str
    study_id: str
    project_id: str
    participants: tuple[ExperimentParticipantSpec, ...]
    model_stack_digest: str
    prompt_generation: str
    workload_digest: str
    seed_digest: str
    repetitions: int
    trial_protocol_id: str
    trial_protocol_configuration_digest: str

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id must be non-empty")
        if not self.study_id.strip():
            raise ValueError("study_id must be non-empty")
        if not self.project_id.strip():
            raise ValueError("project_id must be non-empty")
        for name, value in (("model_stack_digest", self.model_stack_digest), ("workload_digest", self.workload_digest), ("seed_digest", self.seed_digest)):
            require_sha256(value, name)
        if self.repetitions <= 0:
            raise ValueError("repetitions must be positive")
        if not self.trial_protocol_id.strip():
            raise ValueError("trial_protocol_id must be non-empty")
        require_sha256(self.trial_protocol_configuration_digest, "trial_protocol_configuration_digest")

    @property
    def scope(self) -> ScopeIdentity:
        return ScopeIdentity(ScopeKind.EXPERIMENT, self.experiment_id)

    def identity_digest(self) -> str:
        return canonical_digest(self)


__all__ = ["ExperimentParticipantSpec", "ExperimentSpec"]
