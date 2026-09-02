"""Reference multi-agent coordinators with explicit delivery semantics."""

from __future__ import annotations

from collections import deque

from .contracts import (
    CommunicationTopology,
    MultiAgentCancellationPort,
    MultiAgentCheckpoint,
    MultiAgentDeliveryReceipt,
    MultiAgentDeliveryStatus,
    MultiAgentJournalPort,
    MultiAgentMessage,
    MultiAgentNodePort,
    MultiAgentRunResult,
    MultiAgentRunStatus,
)


class MultiAgentCoordinator:
    """Deliver messages over an injected topology with bounded replay state."""

    def __init__(
        self,
        topology: CommunicationTopology,
        nodes: dict[str, MultiAgentNodePort],
        *,
        journal: MultiAgentJournalPort | None = None,
    ) -> None:
        if type(topology) is not CommunicationTopology:
            raise TypeError("multi-agent coordinator requires CommunicationTopology")
        if set(nodes) != set(topology.nodes) or any(
            not callable(getattr(node, "handle", None)) for node in nodes.values()
        ):
            raise ValueError("coordinator nodes must exactly match topology")
        if journal is not None and any(
            not callable(getattr(journal, name, None))
            for name in ("record", "checkpoint")
        ):
            raise TypeError("multi-agent journal must implement record/checkpoint")
        self._topology = topology
        self._nodes = dict(nodes)
        self._journal = journal

    @property
    def topology(self) -> CommunicationTopology:
        return self._topology

    def run(
        self,
        initial: MultiAgentMessage,
        *,
        max_rounds: int = 8,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        return self.run_many(
            (initial,),
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )

    def run_many(
        self,
        initials: tuple[MultiAgentMessage, ...],
        *,
        max_rounds: int = 8,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        self._validate_limits(max_rounds, max_messages)
        if type(initials) is not tuple or not initials:
            raise ValueError("multi-agent initials must be a non-empty tuple")
        conversation_id = initials[0].conversation_id
        if any(
            type(message) is not MultiAgentMessage
            or message.conversation_id != conversation_id
            or message.turn != 0
            or message.causal_parent_ids
            or not self._topology.can_send(message.sender, message.recipient)
            for message in initials
        ):
            raise ValueError("multi-agent initial messages must be topology-valid turn-zero messages")
        if len({message.message_id for message in initials}) != len(initials):
            raise ValueError("multi-agent initial messages must have unique IDs")
        return self._execute(
            deque(initials),
            conversation_id=conversation_id,
            delivered_ids=(),
            start_round=0,
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )

    def resume(
        self,
        checkpoint: MultiAgentCheckpoint,
        *,
        max_rounds: int,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        self._validate_limits(max_rounds, max_messages)
        if type(checkpoint) is not MultiAgentCheckpoint:
            raise TypeError("multi-agent resume requires MultiAgentCheckpoint")
        if checkpoint.topology_digest != self._topology.topology_digest:
            raise ValueError("multi-agent checkpoint topology digest mismatch")
        return self._execute(
            deque(checkpoint.pending),
            conversation_id=checkpoint.conversation_id,
            delivered_ids=checkpoint.delivered_message_ids,
            start_round=checkpoint.round,
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )

    @staticmethod
    def _validate_limits(max_rounds: int, max_messages: int) -> None:
        if type(max_rounds) is not int or max_rounds <= 0:
            raise ValueError("multi-agent max_rounds must be positive")
        if type(max_messages) is not int or max_messages <= 0:
            raise ValueError("multi-agent max_messages must be positive")



    def _execute(
        self,
        queue: deque[MultiAgentMessage],
        *,
        conversation_id: str,
        delivered_ids: tuple[str, ...],
        start_round: int,
        max_rounds: int,
        max_messages: int,
        cancellation: MultiAgentCancellationPort | None,
    ) -> MultiAgentRunResult:
        delivered: list[MultiAgentMessage] = []
        receipts: list[MultiAgentDeliveryReceipt] = []
        seen = set(delivered_ids)
        scheduled = set(seen)
        scheduled.update(message.message_id for message in queue)
        rounds = start_round
        status = MultiAgentRunStatus.COMPLETED
        error: str | None = None
        while queue and rounds < max_rounds:
            if cancellation is not None and cancellation.cancelled():
                status = MultiAgentRunStatus.CANCELLED
                break
            rounds += 1
            current = tuple(queue)
            queue.clear()
            for message in current:
                if len(delivered) >= max_messages:
                    status = MultiAgentRunStatus.MAX_MESSAGES
                    queue.appendleft(message)
                    break
                if message.message_id in seen:
                    receipt = self._receipt(
                        message, MultiAgentDeliveryStatus.DUPLICATE, rounds,
                        "message ID already delivered",
                    )
                    receipts.append(receipt)
                    self._journal_record(message, receipt)
                    continue
                try:
                    self._validate_delivery(message, conversation_id)
                    seen.add(message.message_id)
                    delivered.append(message)
                    outputs = self._nodes[message.recipient].handle(message)
                    if type(outputs) is not tuple or any(
                        type(row) is not MultiAgentMessage for row in outputs
                    ):
                        raise TypeError("multi-agent node must return a tuple of messages")
                    receipt = self._receipt(
                        message, MultiAgentDeliveryStatus.DELIVERED, rounds
                    )
                    receipts.append(receipt)
                    self._journal_record(message, receipt)
                    for output in outputs:
                        disposition = self._validate_output(
                            message, output, conversation_id, scheduled, queue
                        )
                        if disposition is not None:
                            receipts.append(disposition)
                            self._journal_record(output, disposition)
                            continue
                        scheduled.add(output.message_id)
                        queue.append(output)
                except Exception as exc:
                    status = MultiAgentRunStatus.FAILED
                    error = f"{type(exc).__name__}: {exc}"
                    receipt = self._receipt(
                        message, MultiAgentDeliveryStatus.FAILED, rounds, error
                    )
                    receipts.append(receipt)
                    self._journal_record(message, receipt)
                    break
            if status is not MultiAgentRunStatus.COMPLETED:
                break
        if status is MultiAgentRunStatus.COMPLETED and queue:
            status = MultiAgentRunStatus.MAX_ROUNDS
        checkpoint = MultiAgentCheckpoint(
            "multi-agent-checkpoint.v1",
            self._topology.topology_digest,
            conversation_id,
            tuple(queue),
            tuple(message.message_id for message in delivered) + tuple(
                message_id for message_id in delivered_ids if message_id not in {
                    message.message_id for message in delivered
                }
            ),
            rounds,
        )
        if self._journal is not None:
            self._journal.checkpoint(checkpoint)
        return MultiAgentRunResult(
            self._topology.topology_digest,
            tuple(delivered),
            rounds,
            not queue,
            status,
            tuple(receipts),
            checkpoint,
            error,
        )

    def _validate_delivery(
        self, message: MultiAgentMessage, conversation_id: str
    ) -> None:
        if message.conversation_id != conversation_id:
            raise ValueError("message crosses conversation boundary")
        if message.sender not in self._nodes or message.recipient not in self._nodes:
            raise ValueError("message endpoints are not topology nodes")
        if not self._topology.can_send(message.sender, message.recipient):
            raise ValueError("message violates communication topology")

    def _validate_output(
        self,
        parent: MultiAgentMessage,
        output: MultiAgentMessage,
        conversation_id: str,
        scheduled: set[str],
        queue: deque[MultiAgentMessage],
    ) -> MultiAgentDeliveryReceipt | None:
        if output.sender != parent.recipient:
            raise ValueError("node emitted a message with a foreign sender")
        if output.conversation_id != conversation_id:
            raise ValueError("node emitted a cross-conversation message")
        if output.turn != parent.turn + 1:
            raise ValueError("node emitted a non-contiguous message turn")
        if parent.message_id not in output.causal_parent_ids:
            raise ValueError("node output must carry its causal parent message ID")
        if not self._topology.can_send(output.sender, output.recipient):
            raise ValueError("message violates communication topology")
        if output.message_id in scheduled:
            return self._receipt(
                output, MultiAgentDeliveryStatus.DUPLICATE, parent.turn + 1,
                "message ID already scheduled",
            )
        edge = self._topology.edge(output.sender, output.recipient)
        in_flight = sum(
            1 for pending in queue
            if pending.sender == output.sender and pending.recipient == output.recipient
        )
        if in_flight >= edge.max_in_flight:
            return self._receipt(
                output, MultiAgentDeliveryStatus.REJECTED, parent.turn + 1,
                "edge in-flight limit reached",
            )
        return None

    @staticmethod
    def _receipt(
        message: MultiAgentMessage,
        status: MultiAgentDeliveryStatus,
        round_number: int,
        detail: str = "",
    ) -> MultiAgentDeliveryReceipt:
        return MultiAgentDeliveryReceipt(
            message.message_id,
            message.sender,
            message.recipient,
            status,
            message.delivery_attempt,
            round_number,
            detail,
        )

    def _journal_record(
        self, message: MultiAgentMessage, receipt: MultiAgentDeliveryReceipt
    ) -> None:
        if self._journal is not None:
            self._journal.record(message, receipt)



class GroupChatCoordinator:
    """Broadcast a moderator topic to every declared participant."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self._coordinator = coordinator

    def run(
        self,
        moderator: str,
        topic: str,
        *,
        max_rounds: int = 8,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        neighbors = self._coordinator.topology.neighbors(moderator)
        if not neighbors:
            raise ValueError("group chat moderator has no participants")
        return self._coordinator.run_many(
            tuple(MultiAgentMessage(moderator, target, topic, 0) for target in neighbors),
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )


class DebateCoordinator:
    """Debate is an explicit topology and a final judge node."""

    def __init__(self, coordinator: MultiAgentCoordinator, *, judge: str) -> None:
        if type(judge) is not str or not judge.strip():
            raise ValueError("debate judge must be non-empty")
        self._coordinator = coordinator
        self._judge = judge

    def run(
        self,
        proposer: str,
        topic: str,
        *,
        max_rounds: int = 8,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        return self._coordinator.run(
            MultiAgentMessage(proposer, self._judge, topic, 0),
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )


class HierarchicalCoordinator:
    """Manager/worker topology helper with explicit manager identity."""



    def __init__(self, coordinator: MultiAgentCoordinator, *, manager: str) -> None:
        if type(manager) is not str or not manager.strip():
            raise ValueError("hierarchical manager must be non-empty")
        self._coordinator = coordinator
        self._manager = manager

    def run(
        self,
        task: str,
        worker: str,
        *,
        max_rounds: int = 8,
        max_messages: int = 10_000,
        cancellation: MultiAgentCancellationPort | None = None,
    ) -> MultiAgentRunResult:
        return self._coordinator.run(
            MultiAgentMessage(self._manager, worker, task, 0),
            max_rounds=max_rounds,
            max_messages=max_messages,
            cancellation=cancellation,
        )


__all__ = [
    "DebateCoordinator",
    "GroupChatCoordinator",
    "HierarchicalCoordinator",
    "MultiAgentCoordinator",
]
