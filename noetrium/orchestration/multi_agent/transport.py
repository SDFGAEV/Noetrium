"""Transport and membership seams for distributed multi-agent runtimes."""

from __future__ import annotations

from typing import Protocol

from .contracts import (
    CommunicationTopology, MultiAgentJournalPort, MultiAgentMessage,
    MultiAgentNodePort,
)
from .orchestration import MultiAgentCoordinator


class MultiAgentTransportPort(Protocol):
    """Queue/RPC transport owned by the deployment, not the coordinator."""

    def send(self, message: MultiAgentMessage) -> tuple[MultiAgentMessage, ...]: ...


class MultiAgentMembershipPort(Protocol):
    def members(self) -> tuple[str, ...]: ...


class _TransportNode(MultiAgentNodePort):
    def __init__(self, transport: MultiAgentTransportPort) -> None:
        self._transport = transport

    def handle(self, message: MultiAgentMessage) -> tuple[MultiAgentMessage, ...]:
        outputs = self._transport.send(message)
        if type(outputs) is not tuple or any(
            type(item) is not MultiAgentMessage for item in outputs
        ):
            raise TypeError("multi-agent transport must return a tuple of messages")
        return outputs


class TransportBackedMultiAgentCoordinator(MultiAgentCoordinator):
    """Use an external queue/RPC transport while retaining local invariants."""

    def __init__(
        self,
        topology: CommunicationTopology,
        transport: MultiAgentTransportPort,
        *,
        membership: MultiAgentMembershipPort | None = None,
        journal: MultiAgentJournalPort | None = None,
    ) -> None:
        if membership is not None:
            members = membership.members()
            if type(members) is not tuple or set(members) != set(topology.nodes):
                raise ValueError("transport membership must exactly match topology nodes")
        if not callable(getattr(transport, "send", None)):
            raise TypeError("multi-agent transport must implement send()")
        super().__init__(
            topology,
            {node: _TransportNode(transport) for node in topology.nodes},
            journal=journal,
        )


__all__ = [
    "MultiAgentMembershipPort", "MultiAgentTransportPort",
    "TransportBackedMultiAgentCoordinator",
]
