from __future__ import annotations

import pytest

from noetrium_platform.capabilities.participant.agent.api import AgentCoordinationCheckpoint
from noetrium_platform.capabilities.participant.agent.runtime import (
    AgentConversationManager,
    AgentCoordinationHub,
    ConversationKind,
)


def test_pending_conversation_queue_is_bounded() -> None:
    manager = AgentConversationManager(agent_id="agent-a", max_messages=3)
    manager.connect("agent-b")
    for index in range(10):
        manager.receive("agent-b", f"message-{index}", priority=index)

    session = manager.session("agent-b")
    assert session is not None
    assert len(session.messages) == 3
    assert len(session.pending) == 3
    assert [message.text for message in session.pending] == ["message-9", "message-8", "message-7"]


def _hub() -> AgentCoordinationHub:
    hub = AgentCoordinationHub(max_agents=2, max_messages=4)
    hub.register("agent-a")
    hub.register("agent-b")
    hub.set_busy("agent-a", True)
    hub.send("agent-a", "agent-b", "routine", priority=1)
    hub.send("agent-a", "agent-b", "urgent", priority=10, kind=ConversationKind.INTERRUPT)
    return hub


def test_coordination_checkpoint_round_trip_preserves_pending_and_identity() -> None:
    source = _hub()
    encoded = source.checkpoint().to_dict()
    decoded = AgentCoordinationCheckpoint.from_dict(encoded)

    restored = AgentCoordinationHub(max_agents=2, max_messages=4)
    restored.restore(decoded)

    assert restored.status() == source.status()
    pending = restored.pending("agent-b", "agent-a")
    assert [message.text for message in pending] == ["urgent", "routine"]
    assert pending[0].kind is ConversationKind.INTERRUPT

    follow_up = restored.send("agent-a", "agent-b", "after-restart", priority=2)
    assert follow_up.message_id == "conversation:agent-a:2"


def test_coordination_codec_rejects_boolean_generation() -> None:
    document = _hub().checkpoint().to_dict()
    document["peers"][0]["generation"] = True
    with pytest.raises(ValueError, match="generation"):
        AgentCoordinationCheckpoint.from_dict(document)


def test_coordination_restore_capacity_failure_is_transactional() -> None:
    checkpoint = _hub().checkpoint()
    target = AgentCoordinationHub(max_agents=1, max_messages=4)
    target.register("existing")
    before = target.status()

    with pytest.raises(ValueError, match="agent capacity"):
        target.restore(checkpoint)

    assert target.status() == before


def test_conversation_active_peer_survives_restart() -> None:
    source = AgentConversationManager(agent_id="agent-a", max_messages=4)
    source.connect("agent-b")
    source.begin("agent-b")

    target = AgentConversationManager(agent_id="agent-a", max_messages=4)
    target.restore(source.checkpoint())
    response = target.respond("agent-b", "ack")

    assert response.message_id == "conversation:agent-b:0"
    assert target.session("agent-b") is not None
