from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import canonical_digest

from .topology import (
    ParticipantArchitectureRevision,
    ParticipantArchitectureTransition,
    ParticipantTopology,
    ParticipantTopologyTransition,
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _sha256(value: object, field: str) -> str:
    digest = _text(value, field)
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _refs(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise TypeError(f"{field} must be a tuple of non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must be unique")
    return values


@dataclass(frozen=True, slots=True)
class ParticipantStateRevision:
    participant_id: str
    revision_id: str
    state_contract_id: str
    implementation_digest: str
    configuration_digest: str
    state_artifact_digest: str
    predecessor_digest: str | None = None

    def __post_init__(self) -> None:
        _text(self.participant_id, "participant state participant_id")
        _text(self.revision_id, "participant state revision_id")
        _text(self.state_contract_id, "participant state contract id")
        _sha256(self.implementation_digest, "participant state implementation digest")
        _sha256(self.configuration_digest, "participant state configuration digest")
        _sha256(self.state_artifact_digest, "participant state artifact digest")
        if self.predecessor_digest is not None:
            _sha256(self.predecessor_digest, "participant state predecessor digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ParticipantStateTransition:
    transition_id: str
    from_revision_digest: str
    to_revision_digest: str
    update_contract_id: str
    migration_adapter_digest: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.transition_id, "participant state transition id")
        _sha256(self.from_revision_digest, "participant state transition from digest")
        _sha256(self.to_revision_digest, "participant state transition to digest")
        if self.from_revision_digest == self.to_revision_digest:
            raise ValueError("participant state transition must change revision identity")
        _text(self.update_contract_id, "participant state update contract id")
        if self.migration_adapter_digest is not None:
            _sha256(self.migration_adapter_digest, "participant state migration adapter digest")
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs, "participant state evidence refs"))

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ParticipantRevisionProposal:
    proposal_id: str
    predecessor_revision_digest: str
    update_contract_id: str
    reason_digest: str
    migration_adapter_digest: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.proposal_id, "participant revision proposal id")
        _sha256(self.predecessor_revision_digest, "participant revision proposal predecessor digest")
        _text(self.update_contract_id, "participant revision update contract id")
        _sha256(self.reason_digest, "participant revision reason digest")
        if self.migration_adapter_digest is not None:
            _sha256(self.migration_adapter_digest, "participant revision migration adapter digest")
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs, "participant revision evidence refs"))

    def digest(self) -> str:
        return canonical_digest(self)


ParticipantRevisionValue = ParticipantTopology | ParticipantArchitectureRevision | ParticipantStateRevision
ParticipantTransitionValue = ParticipantTopologyTransition | ParticipantArchitectureTransition | ParticipantStateTransition


def _revision_predecessor(candidate: ParticipantRevisionValue) -> str | None:
    if isinstance(candidate, ParticipantTopology):
        return candidate.predecessor_digest
    if isinstance(candidate, ParticipantArchitectureRevision):
        return candidate.predecessor_digest
    return candidate.predecessor_digest


def _transition_digests(transition: ParticipantTransitionValue) -> tuple[str, str]:
    if isinstance(transition, ParticipantTopologyTransition):
        return transition.from_topology_digest, transition.to_topology_digest
    return transition.from_revision_digest, transition.to_revision_digest


@dataclass(frozen=True, slots=True)
class PreparedParticipantRevision:
    proposal: ParticipantRevisionProposal
    predecessor: ParticipantRevisionValue
    candidate: ParticipantRevisionValue
    transition: ParticipantTransitionValue
    preparation_generation: int
    recovery_anchor_digest: str
    validation_plan_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, ParticipantRevisionProposal):
            raise TypeError("prepared participant revision proposal must be typed")
        allowed = (ParticipantTopology, ParticipantArchitectureRevision, ParticipantStateRevision)
        if not isinstance(self.predecessor, allowed) or not isinstance(self.candidate, allowed):
            raise TypeError("prepared participant revisions must be typed")
        if type(self.predecessor) is not type(self.candidate):
            raise TypeError("prepared participant predecessor and candidate must share revision kind")
        predecessor_digest = self.predecessor.digest()
        candidate_digest = self.candidate.digest()
        if self.proposal.predecessor_revision_digest != predecessor_digest:
            raise ValueError("participant proposal does not bind exact predecessor")
        if candidate_digest == predecessor_digest:
            raise ValueError("prepared participant candidate must be a distinct revision")
        if _revision_predecessor(self.candidate) != predecessor_digest:
            raise ValueError("prepared participant candidate does not bind exact predecessor")
        self._validate_transition(predecessor_digest, candidate_digest)
        if type(self.preparation_generation) is not int or self.preparation_generation <= 0:
            raise ValueError("participant preparation generation must be positive")
        _sha256(self.recovery_anchor_digest, "participant revision recovery anchor digest")
        _sha256(self.validation_plan_digest, "participant revision validation plan digest")

    def _validate_transition(self, predecessor_digest: str, candidate_digest: str) -> None:
        expected = {
            ParticipantTopology: ParticipantTopologyTransition,
            ParticipantArchitectureRevision: ParticipantArchitectureTransition,
            ParticipantStateRevision: ParticipantStateTransition,
        }[type(self.candidate)]
        if not isinstance(self.transition, expected):
            raise TypeError("prepared participant transition kind does not match revision kind")
        from_digest, to_digest = _transition_digests(self.transition)
        if from_digest != predecessor_digest or to_digest != candidate_digest:
            raise ValueError("prepared participant transition does not bind predecessor/candidate")
        if isinstance(self.transition, ParticipantStateTransition):
            if self.transition.update_contract_id != self.proposal.update_contract_id:
                raise ValueError("participant state transition update contract drift")
            if self.transition.migration_adapter_digest != self.proposal.migration_adapter_digest:
                raise ValueError("participant state transition migration adapter drift")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ParticipantRevisionCommit:
    prepared: PreparedParticipantRevision
    validation_evidence_digests: tuple[str, ...]
    commit_generation: int

    def __post_init__(self) -> None:
        if not isinstance(self.prepared, PreparedParticipantRevision):
            raise TypeError("participant revision commit must carry prepared revision")
        if not isinstance(self.validation_evidence_digests, tuple) or not self.validation_evidence_digests:
            raise TypeError("participant revision validation evidence must be non-empty tuple")
        for digest in self.validation_evidence_digests:
            _sha256(digest, "participant revision validation evidence digest")
        if len(set(self.validation_evidence_digests)) != len(self.validation_evidence_digests):
            raise ValueError("participant revision validation evidence must be unique")
        if type(self.commit_generation) is not int or self.commit_generation <= 0:
            raise ValueError("participant revision commit generation must be positive")

    @property
    def successor_revision_digest(self) -> str:
        return self.prepared.candidate.digest()

    @property
    def predecessor_revision_digest(self) -> str:
        return self.prepared.predecessor.digest()

    def digest(self) -> str:
        return canonical_digest(self)


__all__ = [
    "ParticipantRevisionCommit",
    "ParticipantRevisionProposal",
    "ParticipantRevisionValue",
    "ParticipantStateRevision",
    "ParticipantStateTransition",
    "ParticipantTransitionValue",
    "PreparedParticipantRevision",
]
