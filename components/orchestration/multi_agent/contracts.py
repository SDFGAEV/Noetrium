"""Higher-tier multi-agent topology and message contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from noetrium_platform.foundation.kernel.kernel import canonical_digest


@dataclass(frozen=True, slots=True, order=True)
class CommunicationEdge:
    sender: str
    recipient: str

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (self.sender, self.recipient)):
            raise ValueError("communication edge endpoints must be non-empty")
        if self.sender == self.recipient:
            raise ValueError("communication edge cannot self-reference")


@dataclass(frozen=True, slots=True)
class CommunicationTopology:
    nodes: tuple[str, ...]
    edges: tuple[CommunicationEdge, ...]
    topology_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple or not self.nodes or any(type(node) is not str or not node.strip() for node in self.nodes):
            raise ValueError("multi-agent topology nodes must be non-empty strings")
        if len(self.nodes) != len(set(self.nodes)):
            raise ValueError("multi-agent topology nodes must be unique")
        known = set(self.nodes)
        if type(self.edges) is not tuple or any(type(edge) is not CommunicationEdge for edge in self.edges):
            raise TypeError("multi-agent topology edges must contain CommunicationEdge")
        if any(edge.sender not in known or edge.recipient not in known for edge in self.edges):
            raise ValueError("communication edge references an unknown node")
        if len(self.edges) != len(set(self.edges)):
            raise ValueError("communication edges must be unique")
        object.__setattr__(self, "topology_digest", canonical_digest({"nodes": self.nodes, "edges": self.edges}))

    def can_send(self, sender: str, recipient: str) -> bool:
        return CommunicationEdge(sender, recipient) in self.edges

    def neighbors(self, sender: str) -> tuple[str, ...]:
        return tuple(sorted(edge.recipient for edge in self.edges if edge.sender == sender))


@dataclass(frozen=True, slots=True)
class MultiAgentMessage:
    sender: str
    recipient: str
    content: str
    turn: int
    message_id: str = field(init=False)

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (self.sender, self.recipient)):
            raise ValueError("multi-agent message endpoints must be non-empty")
        if type(self.content) is not str or not self.content:
            raise ValueError("multi-agent message content must be non-empty")
        if type(self.turn) is not int or isinstance(self.turn, bool) or self.turn < 0:
            raise ValueError("multi-agent message turn must be non-negative")
        object.__setattr__(self, "message_id", canonical_digest({"sender": self.sender, "recipient": self.recipient, "content": self.content, "turn": self.turn}))


class MultiAgentNodePort(Protocol):
    def handle(self, message: MultiAgentMessage) -> tuple[MultiAgentMessage, ...]: ...


@dataclass(frozen=True, slots=True)
class MultiAgentRunResult:
    topology_digest: str
    messages: tuple[MultiAgentMessage, ...]
    rounds: int
    terminated: bool


__all__ = [
    "CommunicationEdge", "CommunicationTopology", "MultiAgentMessage",
    "MultiAgentNodePort", "MultiAgentRunResult",
]
