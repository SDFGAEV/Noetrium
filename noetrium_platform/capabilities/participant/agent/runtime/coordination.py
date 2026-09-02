from __future__ import annotations

from dataclasses import dataclass

from ..api.coordination_checkpoint import AgentCoordinationCheckpoint, AgentPeerCheckpoint
from .conversation import AgentConversationManager, ConversationKind, ConversationMessage


@dataclass(frozen=True, slots=True)
class AgentPeerStatus:
    agent_id: str
    connected: bool = True
    busy: bool = False
    generation: int = 0

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or self.generation < 0:
            raise ValueError("agent peer status is invalid")


class AgentCoordinationHub:
    """Typed in-process hub for the Mindcraft multi-agent topology.

    Transport, process restart and authentication are deliberately outside
    this class. This hub owns only bounded routing, peer status and a
    checkpointable message queue, so a socket/worker provider can replace it
    without changing Agent cognition contracts.
    """

    def __init__(self, *, max_agents: int = 5, max_messages: int = 64) -> None:
        if not 1 <= max_agents <= 5 or max_messages < 1:
            raise ValueError("coordination hub limits are invalid")
        self._max_agents = max_agents
        self._max_messages = max_messages
        self._status: dict[str, AgentPeerStatus] = {}
        self._inboxes: dict[str, AgentConversationManager] = {}

    def register(self, agent_id: str) -> AgentPeerStatus:
        if not agent_id.strip():
            raise ValueError("agent id is required")
        if agent_id not in self._status and len(self._status) >= self._max_agents:
            raise ValueError("coordination hub agent capacity exceeded")
        previous = self._status.get(agent_id, AgentPeerStatus(agent_id))
        status = AgentPeerStatus(agent_id, True, previous.busy, previous.generation + 1)
        self._status[agent_id] = status
        self._inboxes.setdefault(agent_id, AgentConversationManager(agent_id=agent_id, max_messages=self._max_messages))
        return status

    def disconnect(self, agent_id: str) -> AgentPeerStatus:
        status = self._require(agent_id)
        updated = AgentPeerStatus(agent_id, False, status.busy, status.generation)
        self._status[agent_id] = updated
        return updated

    def set_busy(self, agent_id: str, busy: bool) -> AgentPeerStatus:
        status = self._require(agent_id)
        updated = AgentPeerStatus(agent_id, status.connected, bool(busy), status.generation)
        self._status[agent_id] = updated
        return updated

    def send(
        self,
        sender_id: str,
        recipient_id: str,
        text: str,
        *,
        priority: int = 0,
        kind: ConversationKind = ConversationKind.TASK,
    ) -> ConversationMessage:
        sender = self._require(sender_id)
        recipient = self._require(recipient_id)
        if not sender.connected or not recipient.connected:
            raise RuntimeError("cannot route a message through a disconnected peer")
        inbox = self._inboxes[recipient_id]
        inbox.connect(sender_id)
        return inbox.receive(sender_id, text, sender_id=sender_id, priority=priority, generation=recipient.generation, kind=kind)

    def pending(self, agent_id: str, sender_id: str, *, limit: int = 8) -> tuple[ConversationMessage, ...]:
        self._require(agent_id)
        return self._inboxes[agent_id].drain(sender_id, limit=limit)

    def status(self) -> tuple[AgentPeerStatus, ...]:
        return tuple(self._status[key] for key in sorted(self._status))

    def checkpoint(self) -> AgentCoordinationCheckpoint:
        peers = tuple(
            AgentPeerCheckpoint(
                agent_id=status.agent_id,
                connected=status.connected,
                busy=status.busy,
                generation=status.generation,
            )
            for _, status in sorted(self._status.items())
        )
        inboxes = tuple(self._inboxes[agent_id].checkpoint() for agent_id in sorted(self._inboxes))
        return AgentCoordinationCheckpoint(peers=peers, inboxes=inboxes)

    def restore(self, checkpoint: AgentCoordinationCheckpoint) -> None:
        if not isinstance(checkpoint, AgentCoordinationCheckpoint):
            raise TypeError("checkpoint must be an AgentCoordinationCheckpoint")
        if len(checkpoint.peers) > self._max_agents:
            raise ValueError("agent coordination checkpoint exceeds configured agent capacity")
        statuses = {
            peer.agent_id: AgentPeerStatus(peer.agent_id, peer.connected, peer.busy, peer.generation)
            for peer in checkpoint.peers
        }
        inboxes: dict[str, AgentConversationManager] = {}
        for inbox_checkpoint in checkpoint.inboxes:
            inbox = AgentConversationManager(agent_id=inbox_checkpoint.agent_id, max_messages=self._max_messages)
            inbox.restore(inbox_checkpoint)
            inboxes[inbox_checkpoint.agent_id] = inbox
        self._status = statuses
        self._inboxes = inboxes

    def _require(self, agent_id: str) -> AgentPeerStatus:
        try:
            return self._status[agent_id]
        except KeyError as exc:
            raise ValueError(f"unknown agent peer: {agent_id}") from exc


__all__ = ["AgentCoordinationHub", "AgentPeerStatus"]
