from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from research_platform.model.api import (
    ModelPromotionDecision,
    ModelPromotionDisposition,
    ModelPromotionReceipt,
    ModelRevisionCommit,
    ModelRevisionIdentity,
    ModelRollbackReceipt,
    ModelUpdateProposal,
    PreparedModelRevision,
)
from research_platform.platform.kernel import ImmutableModelIdentity


def _model(revision: str) -> ImmutableModelIdentity:
    return ImmutableModelIdentity(
        logical_name="learner", model_id="learner", revision=revision,
        engine="engine", engine_version="1", dtype="bf16", quantization=None,
        context_length=4096, tokenizer_revision="tok-1",
    )


def _initial() -> ModelRevisionIdentity:
    return ModelRevisionIdentity(_model("r1"), "1" * 64)


def _proposal(initial: ModelRevisionIdentity) -> ModelUpdateProposal:
    return ModelUpdateProposal(
        proposal_id="online-update-1",
        predecessor_revision_digest=initial.digest(),
        update_contract_id="paper.online-learning.v1",
        implementation_digest="2" * 64,
        configuration_digest="3" * 64,
        training_input_digest="4" * 64,
        randomness_digest="5" * 64,
        evidence_refs=("artifact:training-cut",),
    )


def _prepared(initial: ModelRevisionIdentity) -> PreparedModelRevision:
    proposal = _proposal(initial)
    candidate = ModelRevisionIdentity(
        _model("r2"), "6" * 64, parent_revision_digest=initial.digest()
    )
    return PreparedModelRevision(
        proposal.digest(), initial.digest(), candidate, 1, "7" * 64, "8" * 64
    )


def test_online_update_prepares_distinct_candidate_without_mutating_predecessor() -> None:
    initial = _initial()
    before = initial.digest()
    prepared = _prepared(initial)
    assert prepared.predecessor_revision_digest == before
    assert prepared.candidate.digest() != before
    assert initial.digest() == before
    with pytest.raises(FrozenInstanceError):
        initial.revision_artifact_digest = "9" * 64  # type: ignore[misc]


def test_prepare_rejects_candidate_not_bound_to_exact_predecessor() -> None:
    initial = _initial()
    proposal = _proposal(initial)
    wrong = ModelRevisionIdentity(_model("r2"), "6" * 64, parent_revision_digest="a" * 64)
    with pytest.raises(ValueError, match="exact predecessor"):
        PreparedModelRevision(
            proposal.digest(), initial.digest(), wrong, 1, "7" * 64, "8" * 64
        )


def test_commit_cannot_swap_prepared_candidate_for_another_successor() -> None:
    initial = _initial()
    prepared = _prepared(initial)
    commit = ModelRevisionCommit(prepared, prepared.candidate, ("9" * 64,), 2)
    assert commit.successor_revision_digest == prepared.candidate.digest()
    other = ModelRevisionIdentity(
        _model("r3"), "a" * 64, parent_revision_digest=initial.digest()
    )
    with pytest.raises(ValueError, match="prepared candidate"):
        ModelRevisionCommit(prepared, other, ("9" * 64,), 2)


def test_promotion_binds_exact_candidate_and_both_evidence_classes() -> None:
    initial = _initial()
    prepared = _prepared(initial)
    decision = ModelPromotionDecision(
        prepared.candidate.digest(), initial.digest(),
        ("b" * 64,), ("c" * 64,), ModelPromotionDisposition.PROMOTE, "d" * 64,
    )
    receipt = ModelPromotionReceipt(decision, 3)
    assert receipt.active_revision_digest == prepared.candidate.digest()
    assert receipt.previous_active_revision_digest == initial.digest()


def test_rejected_candidate_cannot_be_activated() -> None:
    initial = _initial()
    prepared = _prepared(initial)
    decision = ModelPromotionDecision(
        prepared.candidate.digest(), initial.digest(),
        ("b" * 64,), ("c" * 64,), ModelPromotionDisposition.REJECT, "d" * 64,
    )
    with pytest.raises(ValueError, match="cannot be promoted"):
        ModelPromotionReceipt(decision, 3)


def test_rollback_binds_failed_active_target_and_trigger_evidence() -> None:
    initial = _initial()
    prepared = _prepared(initial)
    rollback = ModelRollbackReceipt(
        failed_active_revision_digest=prepared.candidate.digest(),
        rollback_target_revision_digest=initial.digest(),
        triggering_evidence_digests=("e" * 64,),
        recovery_anchor_digest="f" * 64,
        rollback_generation=4,
    )
    assert rollback.rollback_target_revision_digest == initial.digest()
    with pytest.raises(ValueError, match="must differ"):
        ModelRollbackReceipt(
            initial.digest(), initial.digest(), ("e" * 64,), "f" * 64, 4
        )


def test_update_contract_and_evidence_change_identity() -> None:
    initial = _initial()
    a = _proposal(initial)
    b = ModelUpdateProposal(
        a.proposal_id, a.predecessor_revision_digest, "paper.distillation.v1",
        a.implementation_digest, a.configuration_digest, a.training_input_digest,
        a.randomness_digest, a.evidence_refs,
    )
    assert a.digest() != b.digest()
