from __future__ import annotations

import pytest

from research_platform.participant.api import (
    ArchitectureChangeKind,
    ParticipantArchitectureChange,
    ParticipantArchitectureComponent,
    ParticipantArchitectureRevision,
    ParticipantArchitectureTransition,
    ParticipantRevisionCommit,
    ParticipantRevisionProposal,
    ParticipantStateRevision,
    ParticipantStateTransition,
    ParticipantTopology,
    ParticipantTopologyChange,
    ParticipantTopologyMember,
    ParticipantTopologyTransition,
    PreparedParticipantRevision,
    TopologyChangeKind,
)


def _proposal(predecessor_digest: str, contract: str = "paper.self-update.v1") -> ParticipantRevisionProposal:
    return ParticipantRevisionProposal(
        "proposal-1", predecessor_digest, contract, "1" * 64,
        evidence_refs=("artifact:evaluation-plan",),
    )


def _component(config: str = "3") -> ParticipantArchitectureComponent:
    return ParticipantArchitectureComponent("planner", "planner", "2" * 64, config * 64)


def _architectures() -> tuple[ParticipantArchitectureRevision, ParticipantArchitectureRevision, ParticipantArchitectureTransition]:
    before = ParticipantArchitectureRevision("agent-a", "arch-1", (_component("3"),))
    after_component = _component("4")
    after = ParticipantArchitectureRevision(
        "agent-a", "arch-2", (after_component,), predecessor_digest=before.digest()
    )
    change = ParticipantArchitectureChange(
        ArchitectureChangeKind.RECONFIGURE_COMPONENT,
        "planner", before.components[0].digest(), after_component.digest(),
    )
    transition = ParticipantArchitectureTransition(
        "arch-transition-1", "agent-a", before.digest(), after.digest(), (change,)
    )
    return before, after, transition


def _topologies() -> tuple[ParticipantTopology, ParticipantTopology, ParticipantTopologyTransition]:
    arch, _, _ = _architectures()
    before_member = ParticipantTopologyMember(
        "agent-a", "planner", "5" * 64, "6" * 64, arch.digest()
    )
    before = ParticipantTopology("team", (before_member,))
    after_member = ParticipantTopologyMember(
        "agent-a", "planner", "5" * 64, "7" * 64, arch.digest()
    )
    after = ParticipantTopology("team", (after_member,), 2, before.digest())
    change = ParticipantTopologyChange(
        TopologyChangeKind.REBIND_MEMBER,
        "agent-a", before_member.digest(), after_member.digest(),
    )
    transition = ParticipantTopologyTransition(
        "topology-transition-1", before.digest(), after.digest(), (change,)
    )
    return before, after, transition


def test_topology_prepare_is_explicit_recoverable_precommit_state() -> None:
    before, after, transition = _topologies()
    prepared = PreparedParticipantRevision(
        _proposal(before.digest()), before, after, transition, 1, "8" * 64, "9" * 64
    )
    assert prepared.predecessor.digest() == before.digest()
    assert prepared.candidate.digest() == after.digest()
    assert prepared.transition.digest() == transition.digest()
    assert prepared.digest() != after.digest()


def test_participant_commit_exposes_separate_successor_identity() -> None:
    before, after, transition = _topologies()
    prepared = PreparedParticipantRevision(
        _proposal(before.digest()), before, after, transition, 1, "8" * 64, "9" * 64
    )
    commit = ParticipantRevisionCommit(prepared, ("a" * 64,), 2)
    assert commit.predecessor_revision_digest == before.digest()
    assert commit.successor_revision_digest == after.digest()
    assert commit.digest() != prepared.digest()


def test_prepare_rejects_candidate_with_wrong_predecessor() -> None:
    before, after, transition = _topologies()
    wrong = ParticipantTopology(after.topology_id, after.members, 2, "b" * 64)
    with pytest.raises(ValueError, match="exact predecessor"):
        PreparedParticipantRevision(
            _proposal(before.digest()), before, wrong, transition, 1, "8" * 64, "9" * 64
        )


def test_architecture_prepare_rejects_transition_to_another_candidate() -> None:
    before, after, transition = _architectures()
    other = ParticipantArchitectureRevision(
        "agent-a", "arch-3", (_component("5"),), predecessor_digest=before.digest()
    )
    with pytest.raises(ValueError, match="does not bind predecessor/candidate"):
        PreparedParticipantRevision(
            _proposal(before.digest()), before, other, transition, 1, "8" * 64, "9" * 64
        )


def test_state_update_binds_open_contract_and_migration_identity() -> None:
    before = ParticipantStateRevision(
        "agent-a", "state-1", "paper.memory-state.v1", "2" * 64, "3" * 64, "4" * 64
    )
    after = ParticipantStateRevision(
        "agent-a", "state-2", "paper.memory-state.v1", "2" * 64, "5" * 64, "6" * 64,
        predecessor_digest=before.digest(),
    )
    proposal = ParticipantRevisionProposal(
        "proposal-state", before.digest(), "paper.online-memory-update.v7", "7" * 64,
        migration_adapter_digest="8" * 64,
    )
    transition = ParticipantStateTransition(
        "state-transition", before.digest(), after.digest(), proposal.update_contract_id,
        migration_adapter_digest=proposal.migration_adapter_digest,
    )
    prepared = PreparedParticipantRevision(
        proposal, before, after, transition, 3, "9" * 64, "a" * 64
    )
    assert prepared.candidate.digest() == after.digest()
    assert proposal.update_contract_id == "paper.online-memory-update.v7"


def test_state_prepare_rejects_update_contract_or_adapter_drift() -> None:
    before = ParticipantStateRevision(
        "agent-a", "state-1", "paper.state.v1", "2" * 64, "3" * 64, "4" * 64
    )
    after = ParticipantStateRevision(
        "agent-a", "state-2", "paper.state.v1", "2" * 64, "5" * 64, "6" * 64,
        predecessor_digest=before.digest(),
    )
    proposal = ParticipantRevisionProposal(
        "proposal-state", before.digest(), "paper.update.v1", "7" * 64,
        migration_adapter_digest="8" * 64,
    )
    drifted = ParticipantStateTransition(
        "state-transition", before.digest(), after.digest(), "paper.update.v2",
        migration_adapter_digest="8" * 64,
    )
    with pytest.raises(ValueError, match="update contract drift"):
        PreparedParticipantRevision(
            proposal, before, after, drifted, 3, "9" * 64, "a" * 64
        )
