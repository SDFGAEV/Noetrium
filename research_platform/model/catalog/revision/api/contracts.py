from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import ImmutableModelIdentity, canonical_digest


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _sha256(value: object, field: str) -> str:
    digest = _text(value, field)
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _digests(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise TypeError(f"{field} must be a non-empty tuple")
    for value in values:
        _sha256(value, field)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")
    return values


@dataclass(frozen=True, slots=True)
class ModelRevisionIdentity:
    model: ImmutableModelIdentity
    revision_artifact_digest: str
    parent_revision_digest: str | None = None
    lineage_contract_id: str = "model-revision.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.model, ImmutableModelIdentity):
            raise TypeError("model revision identity must carry ImmutableModelIdentity")
        _sha256(self.revision_artifact_digest, "model revision artifact digest")
        _text(self.lineage_contract_id, "model revision lineage contract id")
        if self.parent_revision_digest is not None:
            _sha256(self.parent_revision_digest, "model revision parent digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ModelUpdateProposal:
    proposal_id: str
    predecessor_revision_digest: str
    update_contract_id: str
    implementation_digest: str
    configuration_digest: str
    training_input_digest: str
    randomness_digest: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.proposal_id, "model update proposal id")
        _sha256(self.predecessor_revision_digest, "model update predecessor digest")
        _text(self.update_contract_id, "model update contract id")
        _sha256(self.implementation_digest, "model update implementation digest")
        _sha256(self.configuration_digest, "model update configuration digest")
        _sha256(self.training_input_digest, "model update training input digest")
        if self.randomness_digest is not None:
            _sha256(self.randomness_digest, "model update randomness digest")
        if not isinstance(self.evidence_refs, tuple) or any(
            not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs
        ):
            raise TypeError("model update evidence refs must be non-empty strings")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("model update evidence refs must be unique")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class PreparedModelRevision:
    proposal_digest: str
    predecessor_revision_digest: str
    candidate: ModelRevisionIdentity
    preparation_generation: int
    recovery_anchor_digest: str
    validation_plan_digest: str

    def __post_init__(self) -> None:
        _sha256(self.proposal_digest, "prepared model proposal digest")
        _sha256(self.predecessor_revision_digest, "prepared model predecessor digest")
        if not isinstance(self.candidate, ModelRevisionIdentity):
            raise TypeError("prepared model candidate must be ModelRevisionIdentity")
        if self.candidate.parent_revision_digest != self.predecessor_revision_digest:
            raise ValueError("prepared model candidate must bind the exact predecessor revision")
        if self.candidate.digest() == self.predecessor_revision_digest:
            raise ValueError("prepared model candidate must be a distinct revision")
        if type(self.preparation_generation) is not int or self.preparation_generation <= 0:
            raise ValueError("prepared model generation must be positive")
        _sha256(self.recovery_anchor_digest, "prepared model recovery anchor digest")
        _sha256(self.validation_plan_digest, "prepared model validation plan digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ModelRevisionCommit:
    prepared: PreparedModelRevision
    successor: ModelRevisionIdentity
    validation_evidence_digests: tuple[str, ...]
    commit_generation: int

    def __post_init__(self) -> None:
        if not isinstance(self.prepared, PreparedModelRevision):
            raise TypeError("model commit must carry PreparedModelRevision")
        if not isinstance(self.successor, ModelRevisionIdentity):
            raise TypeError("model commit successor must be ModelRevisionIdentity")
        if self.successor.digest() != self.prepared.candidate.digest():
            raise ValueError("model commit successor must equal the prepared candidate")
        _digests(self.validation_evidence_digests, "model commit validation evidence")
        if type(self.commit_generation) is not int or self.commit_generation <= 0:
            raise ValueError("model commit generation must be positive")

    @property
    def successor_revision_digest(self) -> str:
        return self.successor.digest()

    def digest(self) -> str:
        return canonical_digest(self)


class ModelPromotionDisposition(StrEnum):
    PROMOTE = "promote"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ModelPromotionDecision:
    candidate_revision_digest: str
    predecessor_active_revision_digest: str
    qualification_evidence_digests: tuple[str, ...]
    evaluation_evidence_digests: tuple[str, ...]
    disposition: ModelPromotionDisposition
    reason_digest: str

    def __post_init__(self) -> None:
        _sha256(self.candidate_revision_digest, "model promotion candidate digest")
        _sha256(self.predecessor_active_revision_digest, "model promotion predecessor digest")
        if self.candidate_revision_digest == self.predecessor_active_revision_digest:
            raise ValueError("model promotion candidate must differ from active predecessor")
        _digests(self.qualification_evidence_digests, "model promotion qualification evidence")
        _digests(self.evaluation_evidence_digests, "model promotion evaluation evidence")
        if not isinstance(self.disposition, ModelPromotionDisposition):
            raise TypeError("model promotion disposition must be typed")
        _sha256(self.reason_digest, "model promotion reason digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ModelPromotionReceipt:
    decision: ModelPromotionDecision
    activation_generation: int

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ModelPromotionDecision):
            raise TypeError("model promotion receipt must carry ModelPromotionDecision")
        if self.decision.disposition is not ModelPromotionDisposition.PROMOTE:
            raise ValueError("rejected model revision cannot be promoted")
        if type(self.activation_generation) is not int or self.activation_generation <= 0:
            raise ValueError("model promotion activation generation must be positive")

    @property
    def active_revision_digest(self) -> str:
        return self.decision.candidate_revision_digest

    @property
    def previous_active_revision_digest(self) -> str:
        return self.decision.predecessor_active_revision_digest

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ModelRollbackReceipt:
    failed_active_revision_digest: str
    rollback_target_revision_digest: str
    triggering_evidence_digests: tuple[str, ...]
    recovery_anchor_digest: str
    rollback_generation: int

    def __post_init__(self) -> None:
        _sha256(self.failed_active_revision_digest, "model rollback failed revision digest")
        _sha256(self.rollback_target_revision_digest, "model rollback target digest")
        if self.failed_active_revision_digest == self.rollback_target_revision_digest:
            raise ValueError("model rollback target must differ from failed active revision")
        _digests(self.triggering_evidence_digests, "model rollback triggering evidence")
        _sha256(self.recovery_anchor_digest, "model rollback recovery anchor digest")
        if type(self.rollback_generation) is not int or self.rollback_generation <= 0:
            raise ValueError("model rollback generation must be positive")

    def digest(self) -> str:
        return canonical_digest(self)


@runtime_checkable
class ModelUpdateProducerPort(Protocol):
    def prepare_update(self, proposal: ModelUpdateProposal) -> PreparedModelRevision: ...


@runtime_checkable
class ModelRevisionAuthorityPort(Protocol):
    def commit_successor(
        self, prepared: PreparedModelRevision, validation_evidence_digests: tuple[str, ...],
        *, commit_generation: int,
    ) -> ModelRevisionCommit: ...

    def promote(
        self, decision: ModelPromotionDecision, *, activation_generation: int
    ) -> ModelPromotionReceipt: ...

    def rollback(
        self, failed_active_revision_digest: str, rollback_target_revision_digest: str,
        triggering_evidence_digests: tuple[str, ...], *, recovery_anchor_digest: str, rollback_generation: int,
    ) -> ModelRollbackReceipt: ...


__all__ = [
    "ModelPromotionDecision",
    "ModelPromotionDisposition",
    "ModelPromotionReceipt",
    "ModelRevisionAuthorityPort",
    "ModelRevisionCommit",
    "ModelRevisionIdentity",
    "ModelRollbackReceipt",
    "ModelUpdateProducerPort",
    "ModelUpdateProposal",
    "PreparedModelRevision",
]
