"""Higher-tier multi-agent coordinators.

Single-agent components decide within one agent. These coordinators own only
message delivery over an injected topology; agent state and scientific truth
remain node-owned.
"""

from __future__ import annotations

from collections import deque

from .contracts import (
    CommunicationTopology,
    MultiAgentMessage,
    MultiAgentNodePort,
    MultiAgentRunResult,
)


class MultiAgentCoordinator:
    def __init__(
        self,
        topology: CommunicationTopology,
        nodes: dict[str, MultiAgentNodePort],
    ) -> None:
        if type(topology) is not CommunicationTopology:
            raise TypeError("multi-agent coordinator requires CommunicationTopology")
        if set(nodes) != set(topology.nodes) or any(not callable(getattr(node, "handle", None)) for node in nodes.values()):
            raise ValueError("coordinator nodes must exactly match topology")
        self._topology = topology
        self._nodes = dict(nodes)

    @property
    def topology(self) -> CommunicationTopology:
        return self._topology

    def run(self, initial: MultiAgentMessage, *, max_rounds: int = 8) -> MultiAgentRunResult:
        if type(initial) is not MultiAgentMessage:
            raise TypeError("multi-agent initial message must be MultiAgentMessage")
        if initial.recipient not in self._nodes or initial.sender not in self._nodes:
            raise ValueError("initial message endpoints are not topology nodes")
        if not self._topology.can_send(initial.sender, initial.recipient):
            raise ValueError("initial message violates communication topology")
        if type(max_rounds) is not int or max_rounds <= 0:
            raise ValueError("multi-agent max_rounds must be positive")
        queue = deque((initial,))
        delivered: list[MultiAgentMessage] = []
        rounds = 0
        while queue and rounds < max_rounds:
            rounds += 1
            current = tuple(queue)
            queue.clear()
            for message in current:
                delivered.append(message)
                outputs = self._nodes[message.recipient].handle(message)
                if type(outputs) is not tuple or any(type(row) is not MultiAgentMessage for row in outputs):
                    raise TypeError("multi-agent node must return a tuple of messages")
                for output in outputs:
                    if output.sender != message.recipient:
                        raise ValueError("node emitted a message with a foreign sender")
                    if output.turn < rounds:
                        raise ValueError("node emitted a stale message turn")
                    if not self._topology.can_send(output.sender, output.recipient):
                        raise ValueError("message violates communication topology")
                    queue.append(output)
        return MultiAgentRunResult(
            self._topology.topology_digest,
            tuple(delivered),
            rounds,
            not queue,
        )


class GroupChatCoordinator:
    """Broadcast topology helper; edges still enforce every delivery."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self._coordinator = coordinator

    def run(self, moderator: str, topic: str, *, max_rounds: int = 8) -> MultiAgentRunResult:
        neighbors = self._coordinator.topology.neighbors(moderator)
        if not neighbors:
            raise ValueError("group chat moderator has no participants")
        return self._coordinator.run(
            MultiAgentMessage(moderator, neighbors[0], topic, 0),
            max_rounds=max_rounds,
        )


class DebateCoordinator:
    """Debate is an explicit topology and a final judge node, not a hidden bus."""

    def __init__(self, coordinator: MultiAgentCoordinator, *, judge: str) -> None:
        if type(judge) is not str or not judge.strip():
            raise ValueError("debate judge must be non-empty")
        self._coordinator = coordinator
        self._judge = judge

    def run(self, proposer: str, topic: str, *, max_rounds: int = 8) -> MultiAgentRunResult:
        return self._coordinator.run(
            MultiAgentMessage(proposer, self._judge, topic, 0),
            max_rounds=max_rounds,
        )


class HierarchicalCoordinator:
    """Manager/worker topology helper with explicit manager identity."""

    def __init__(self, coordinator: MultiAgentCoordinator, *, manager: str) -> None:
        if type(manager) is not str or not manager.strip():
            raise ValueError("hierarchical manager must be non-empty")
        self._coordinator = coordinator
        self._manager = manager

    def run(self, task: str, worker: str, *, max_rounds: int = 8) -> MultiAgentRunResult:
        return self._coordinator.run(
            MultiAgentMessage(self._manager, worker, task, 0),
            max_rounds=max_rounds,
        )


__all__ = [
    "DebateCoordinator", "GroupChatCoordinator", "HierarchicalCoordinator",
    "MultiAgentCoordinator",
]
