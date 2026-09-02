from __future__ import annotations

import pytest

from noetrium_platform.capabilities.participant.agent.api import (
    AGENT_MEMORY_CHECKPOINT_SCHEMA,
    AgentActionSequence,
    AgentActionStep,
    AgentMemoryCheckpoint,
    AgentStepReceipt,
)
from noetrium_platform.capabilities.participant.agent.runtime import InMemoryAgentMemory
from noetrium_platform.foundation.kernel.kernel import ExecutionContext


def _context() -> ExecutionContext:
    return ExecutionContext("run", "trace", "span", participant_generations=(("environment", "world-v1"),))


def _receipt(index: int) -> AgentStepReceipt:
    return AgentStepReceipt(
        f"action:{index}",
        "move",
        "skill.move",
        f"sequence:{index}",
        True,
        True,
        effect_certainty="confirmed",
    )

def test_checkpoint_round_trip_preserves_sequence_identity() -> None:
    memory = InMemoryAgentMemory()
    memory.record(_receipt(1), _context())
    memory.record(_receipt(2), _context())

    checkpoint = memory.checkpoint()
    encoded = checkpoint.to_dict()
    assert encoded["schema_version"] == AGENT_MEMORY_CHECKPOINT_SCHEMA

    restored = InMemoryAgentMemory()
    restored.restore(AgentMemoryCheckpoint.from_dict(encoded))
    restored.record(_receipt(3), _context())

    assert [record.memory_id for record in restored.records] == [
        "memory:episode:1",
        "memory:episode:2",
        "memory:episode:3",
    ]


def test_checkpoint_codec_rejects_lossy_coercions_and_unknown_fields() -> None:
    memory = InMemoryAgentMemory()
    memory.record(_receipt(1), _context())
    encoded = memory.checkpoint().to_dict()

    wrong_verified = dict(encoded)
    wrong_verified["records"] = [dict(encoded["records"][0], verified="false")]
    with pytest.raises(ValueError, match="verified"):
        AgentMemoryCheckpoint.from_dict(wrong_verified)

    wrong_counter = dict(encoded, sequence_counter=True)
    with pytest.raises(ValueError, match="sequence_counter"):
        AgentMemoryCheckpoint.from_dict(wrong_counter)

    unknown_field = dict(encoded, legacy=True)
    with pytest.raises(ValueError, match="fields mismatch"):
        AgentMemoryCheckpoint.from_dict(unknown_field)


def test_restore_capacity_failure_is_transactional() -> None:
    source = InMemoryAgentMemory(max_records=2)
    source.record(_receipt(1), _context())
    source.record(_receipt(2), _context())
    checkpoint = source.checkpoint()

    target = InMemoryAgentMemory(max_records=1)
    target.record(_receipt(9), _context())
    before = target.snapshot()

    with pytest.raises(ValueError, match="capacity"):
        target.restore(checkpoint)
    assert target.snapshot() == before

    target.record(_receipt(10), _context())
    assert target.records[-1].memory_id == "memory:episode:2"


def test_skill_sequence_requires_effect_verification_for_trusted_memory() -> None:
    memory = InMemoryAgentMemory()
    sequence = AgentActionSequence(
        "sequence:trusted",
        "skill.move",
        (AgentActionStep("action:trusted", "move", {}, "skill.move", "sequence:trusted", 0),),
    )
    unverified = AgentStepReceipt(
        "action:trusted", "move", "skill.move", "sequence:trusted", True, False,
        effect_certainty="rejected",
    )
    memory.record_sequence(sequence, (unverified,), success=True, context=_context())
    assert memory.records[-1].kind == "skill_episode"
    assert memory.records[-1].verified is False
