from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


AGENT_COORDINATION_CHECKPOINT_SCHEMA = "agent-coordination.v2"
_CONVERSATION_STATES = frozenset({"disconnected", "idle", "active", "waiting"})
_CONVERSATION_KINDS = frozenset({"chat", "task", "interrupt", "system"})


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _exact(document: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(document)
    if actual != expected:
        raise ValueError(f"{label} fields mismatch: expected={sorted(expected)!r} actual={sorted(actual)!r}")


def _metadata(value: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ValueError("message metadata must be a mapping")
    rows: list[tuple[str, str]] = []
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError("message metadata must contain only string pairs")
        rows.append((key, item))
    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class AgentConversationMessageCheckpoint:
    message_id: str
    peer_id: str
    sender_id: str
    text: str
    turn: int
    metadata: tuple[tuple[str, str], ...]
    priority: int
    generation: int
    kind: str

    def __post_init__(self) -> None:
        for name in ("message_id", "peer_id", "sender_id", "text"):
            _string(getattr(self, name), name)
        _integer(self.turn, "turn")
        _integer(self.priority, "priority")
        _integer(self.generation, "generation")
        if self.kind not in _CONVERSATION_KINDS:
            raise ValueError("conversation message kind is invalid")
        if tuple(sorted(self.metadata)) != self.metadata:
            raise ValueError("message metadata must be sorted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "peer_id": self.peer_id,
            "sender_id": self.sender_id,
            "text": self.text,
            "turn": self.turn,
            "metadata": dict(self.metadata),
            "priority": self.priority,
            "generation": self.generation,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentConversationMessageCheckpoint":
        _exact(document, frozenset({"message_id", "peer_id", "sender_id", "text", "turn", "metadata", "priority", "generation", "kind"}), "conversation message checkpoint")
        kind = _string(document["kind"], "kind")
        if kind not in _CONVERSATION_KINDS:
            raise ValueError("conversation message kind is invalid")
        return cls(
            message_id=_string(document["message_id"], "message_id"),
            peer_id=_string(document["peer_id"], "peer_id"),
            sender_id=_string(document["sender_id"], "sender_id"),
            text=_string(document["text"], "text"),
            turn=_integer(document["turn"], "turn"),
            metadata=_metadata(document["metadata"]),
            priority=_integer(document["priority"], "priority"),
            generation=_integer(document["generation"], "generation"),
            kind=kind,
        )


@dataclass(frozen=True, slots=True)
class AgentConversationSessionCheckpoint:
    peer_id: str
    state: str
    messages: tuple[AgentConversationMessageCheckpoint, ...]
    next_turn: int
    last_error: str
    pending: tuple[AgentConversationMessageCheckpoint, ...]

    def __post_init__(self) -> None:
        _string(self.peer_id, "peer_id")
        if self.state not in _CONVERSATION_STATES:
            raise ValueError("conversation state is invalid")
        _integer(self.next_turn, "next_turn")
        if not isinstance(self.last_error, str):
            raise ValueError("last_error must be a string")
        if any(message.peer_id != self.peer_id for message in (*self.messages, *self.pending)):
            raise ValueError("conversation checkpoint message peer mismatch")
        if any(message.turn >= self.next_turn for message in (*self.messages, *self.pending)):
            raise ValueError("conversation checkpoint next_turn must exceed stored turns")

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "state": self.state,
            "messages": [message.to_dict() for message in self.messages],
            "next_turn": self.next_turn,
            "last_error": self.last_error,
            "pending": [message.to_dict() for message in self.pending],
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentConversationSessionCheckpoint":
        _exact(document, frozenset({"peer_id", "state", "messages", "next_turn", "last_error", "pending"}), "conversation session checkpoint")
        state = _string(document["state"], "state")
        if state not in _CONVERSATION_STATES:
            raise ValueError("conversation state is invalid")
        messages = _message_rows(document["messages"], "messages")
        pending = _message_rows(document["pending"], "pending")
        last_error = document["last_error"]
        if not isinstance(last_error, str):
            raise ValueError("last_error must be a string")
        return cls(
            peer_id=_string(document["peer_id"], "peer_id"),
            state=state,
            messages=messages,
            next_turn=_integer(document["next_turn"], "next_turn"),
            last_error=last_error,
            pending=pending,
        )


def _message_rows(value: Any, field: str) -> tuple[AgentConversationMessageCheckpoint, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a sequence")
    result: list[AgentConversationMessageCheckpoint] = []
    for row in value:
        if not isinstance(row, Mapping):
            raise ValueError(f"{field} entries must be mappings")
        result.append(AgentConversationMessageCheckpoint.from_dict(row))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class AgentConversationCheckpoint:
    agent_id: str
    active_peer: str | None
    sessions: tuple[AgentConversationSessionCheckpoint, ...]

    def __post_init__(self) -> None:
        _string(self.agent_id, "agent_id")
        if self.active_peer is not None and (not isinstance(self.active_peer, str) or not self.active_peer.strip()):
            raise ValueError("active_peer must be None or a non-empty string")
        peer_ids = tuple(session.peer_id for session in self.sessions)
        if len(peer_ids) != len(set(peer_ids)):
            raise ValueError("conversation checkpoint contains duplicate peers")
        if self.active_peer is not None and self.active_peer not in peer_ids:
            raise ValueError("active_peer must reference a stored session")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "active_peer": self.active_peer,
            "sessions": [session.to_dict() for session in self.sessions],
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentConversationCheckpoint":
        _exact(document, frozenset({"agent_id", "active_peer", "sessions"}), "conversation checkpoint")
        active_peer = document["active_peer"]
        if active_peer is not None and (not isinstance(active_peer, str) or not active_peer.strip()):
            raise ValueError("active_peer must be None or a non-empty string")
        rows = document["sessions"]
        if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
            raise ValueError("sessions must be a sequence")
        sessions = tuple(AgentConversationSessionCheckpoint.from_dict(row) for row in rows if isinstance(row, Mapping))
        if len(sessions) != len(rows):
            raise ValueError("sessions entries must be mappings")
        return cls(_string(document["agent_id"], "agent_id"), active_peer, sessions)


@dataclass(frozen=True, slots=True)
class AgentPeerCheckpoint:
    agent_id: str
    connected: bool
    busy: bool
    generation: int

    def __post_init__(self) -> None:
        _string(self.agent_id, "agent_id")
        _boolean(self.connected, "connected")
        _boolean(self.busy, "busy")
        _integer(self.generation, "generation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "connected": self.connected,
            "busy": self.busy,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentPeerCheckpoint":
        _exact(document, frozenset({"agent_id", "connected", "busy", "generation"}), "peer checkpoint")
        return cls(
            _string(document["agent_id"], "agent_id"),
            _boolean(document["connected"], "connected"),
            _boolean(document["busy"], "busy"),
            _integer(document["generation"], "generation"),
        )


@dataclass(frozen=True, slots=True)
class AgentCoordinationCheckpoint:
    peers: tuple[AgentPeerCheckpoint, ...]
    inboxes: tuple[AgentConversationCheckpoint, ...]
    schema_version: str = AGENT_COORDINATION_CHECKPOINT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != AGENT_COORDINATION_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent coordination checkpoint schema")
        peer_ids = tuple(peer.agent_id for peer in self.peers)
        inbox_ids = tuple(inbox.agent_id for inbox in self.inboxes)
        if len(peer_ids) != len(set(peer_ids)) or len(inbox_ids) != len(set(inbox_ids)):
            raise ValueError("agent coordination checkpoint contains duplicate identities")
        if set(peer_ids) != set(inbox_ids):
            raise ValueError("agent coordination peers and inboxes must have identical identities")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "peers": [peer.to_dict() for peer in self.peers],
            "inboxes": [inbox.to_dict() for inbox in self.inboxes],
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentCoordinationCheckpoint":
        _exact(document, frozenset({"schema_version", "peers", "inboxes"}), "agent coordination checkpoint")
        if document["schema_version"] != AGENT_COORDINATION_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent coordination checkpoint schema")
        peers_value = document["peers"]
        inboxes_value = document["inboxes"]
        if isinstance(peers_value, (str, bytes, bytearray)) or not isinstance(peers_value, Sequence):
            raise ValueError("peers must be a sequence")
        if isinstance(inboxes_value, (str, bytes, bytearray)) or not isinstance(inboxes_value, Sequence):
            raise ValueError("inboxes must be a sequence")
        if any(not isinstance(row, Mapping) for row in (*peers_value, *inboxes_value)):
            raise ValueError("coordination checkpoint rows must be mappings")
        return cls(
            peers=tuple(AgentPeerCheckpoint.from_dict(row) for row in peers_value),
            inboxes=tuple(AgentConversationCheckpoint.from_dict(row) for row in inboxes_value),
        )


__all__ = [
    "AGENT_COORDINATION_CHECKPOINT_SCHEMA",
    "AgentConversationCheckpoint",
    "AgentConversationMessageCheckpoint",
    "AgentConversationSessionCheckpoint",
    "AgentCoordinationCheckpoint",
    "AgentPeerCheckpoint",
]
