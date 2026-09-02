from __future__ import annotations

from components.reference.single_agent.agent import (
    ReferenceAgentAction,
    ReferenceAgentActionKind,
    ReferenceAgentDecision,
    ReferenceAgentMessage,
    ReferenceAgentStatus,
    ReferenceReActMethod,
    ReferenceToolRegistryPort,
)
from components.reference.single_agent.memory import MemoryItem, VectorMemoryStore, WorkingMemory
from orchestration.multi_agent import (
    CommunicationEdge,
    CommunicationTopology,
    GroupChatCoordinator,
    MultiAgentCoordinator,
    MultiAgentMessage,
    MultiAgentRunStatus,
)
from components.reference.single_agent.tools import (
    ToolArguments,
    ToolAuthorization,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolRiskClass,
)


class _Policy:
    def decide(self, state):
        if state.step == 0:
            return ReferenceAgentDecision(
                ReferenceAgentAction(
                    ReferenceAgentActionKind.TOOL,
                    "echo",
                    (("value", "observed"),),
                    "use echo",
                )
            )
        return ReferenceAgentDecision(ReferenceAgentAction(ReferenceAgentActionKind.FINAL, "answer", content="done"))


def test_react_is_importable_and_tool_registry_is_explicit() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("echo", "return text", "tool.echo.v1"),
        lambda arguments: ToolResult("echo", True, arguments.as_mapping()["value"]),
    )
    result = ReferenceReActMethod(_Policy(), ReferenceToolRegistryPort(registry)).run("task", max_steps=3)
    assert result.status is ReferenceAgentStatus.COMPLETED
    assert result.answer == "done"
    assert registry.definitions()[0].name == "echo"


def test_working_and_vector_memory_are_bounded_and_deterministic() -> None:
    working = WorkingMemory(capacity=2)
    working.remember(MemoryItem("a", "first", embedding=(1.0, 0.0)))
    working.remember(MemoryItem("b", "second", embedding=(0.0, 1.0)))
    working.remember(MemoryItem("c", "third", embedding=(1.0, 1.0)))
    assert tuple(item.memory_id for item in working.items()) == ("b", "c")
    vector = VectorMemoryStore(dimension=2)
    vector.upsert(MemoryItem("x", "x", embedding=(1.0, 0.0)))
    vector.upsert(MemoryItem("y", "y", embedding=(0.0, 1.0)))
    assert vector.search((1.0, 0.0), limit=1)[0][0].memory_id == "x"


class _Node:
    def __init__(self, name: str) -> None:
        self.name = name

    def handle(self, message: MultiAgentMessage) -> tuple[MultiAgentMessage, ...]:
        if message.turn >= 2:
            return ()
        target = "worker" if self.name == "manager" else "manager"
        return (MultiAgentMessage(
            self.name,
            target,
            f"reply:{message.content}",
            message.turn + 1,
            causal_parent_ids=(message.message_id,),
        ),)


def test_multi_agent_layer_delivers_only_over_declared_topology() -> None:
    topology = CommunicationTopology(
        ("manager", "worker"),
        (CommunicationEdge("manager", "worker"), CommunicationEdge("worker", "manager")),
    )
    coordinator = MultiAgentCoordinator(
        topology,
        {"manager": _Node("manager"), "worker": _Node("worker")},
    )
    result = coordinator.run(MultiAgentMessage("manager", "worker", "task", 0), max_rounds=4)
    assert result.topology_digest == topology.topology_digest
    assert result.terminated is True
    assert [message.recipient for message in result.messages] == ["worker", "manager", "worker"]


def test_component_stress_retrieval_and_tool_calls_remain_bounded() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from time import perf_counter
    from components.reference.single_agent.memory import EpisodicMemoryStore

    started = perf_counter()
    episodes = EpisodicMemoryStore()
    for index in range(4096):
        episodes.put(MemoryItem(f"episode-{index:05d}", f"trajectory-{index}", ("agent",)))
    assert len(episodes.search("trajectory-", limit=4096)) == 4096
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("identity", "return value", "tool.identity.v1"),
        lambda arguments: ToolResult("identity", True, arguments.as_mapping()["value"]),
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda index: registry.invoke(
                "identity",
                ToolArguments(
                    (("value", f"v-{index}"),)
                ),
            ),
            range(1024),
        ))
    assert all(result.success for result in results)
    assert perf_counter() - started < 20.0


def test_tool_capability_risk_is_default_deny_and_audited() -> None:
    definition = ToolDefinition(
        "write-file",
        "write a file",
        "tool.write.v1",
        capability_id="filesystem.write",
        risk_class=ToolRiskClass.HIGH_RISK,
        sandbox_profile="isolated",
    )
    calls = []
    denied = ToolRegistry()
    denied.register(definition, lambda _arguments: calls.append(True) or ToolResult("write-file", True, "done"))
    result = denied.invoke("write-file", ToolArguments.from_mapping({"path": "x"}))
    assert result.success is False
    assert "explicit authorization" in (result.error or "")
    assert calls == []

    audit_rows = []
    class Authorizer:
        def review(self, item, arguments):
            assert item is definition
            assert arguments.as_mapping()["path"] == "x"
            return ToolAuthorization("filesystem.write", True, "approved for test", "approval-1")

    class Audit:
        def record(self, item, arguments, item_result):
            audit_rows.append((item.definition_digest, arguments.digest, item_result.result_digest))

    allowed = ToolRegistry(authorization=Authorizer(), audit=Audit())
    allowed.register(definition, lambda _arguments: ToolResult("write-file", True, "done"))
    result = allowed.invoke("write-file", ToolArguments.from_mapping({"path": "x"}))
    assert result.success is True
    assert len(audit_rows) == 1


def test_memory_namespaces_isolate_same_ids_and_vector_results() -> None:
    from components.reference.single_agent.memory import EpisodicMemoryStore

    episodes = EpisodicMemoryStore()
    episodes.put(MemoryItem("same", "alpha", namespace="paper-a"))
    episodes.put(MemoryItem("same", "beta", namespace="paper-b"))
    assert episodes.get("same", namespace="paper-a").content == "alpha"
    assert episodes.get("same", namespace="paper-b").content == "beta"

    vectors = VectorMemoryStore(dimension=2)
    vectors.upsert(MemoryItem("same", "alpha", namespace="paper-a", embedding=(1.0, 0.0)))
    vectors.upsert(MemoryItem("same", "beta", namespace="paper-b", embedding=(0.0, 1.0)))
    assert tuple(
        row[0].namespace for row in vectors.search((0.0, 1.0), namespace="paper-b")
    ) == ("paper-b",)


def test_multi_agent_checkpoint_resume_preserves_transcript_and_retry_identity() -> None:
    topology = CommunicationTopology(
        ("manager", "worker"),
        (CommunicationEdge("manager", "worker"), CommunicationEdge("worker", "manager")),
    )
    coordinator = MultiAgentCoordinator(
        topology,
        {"manager": _Node("manager"), "worker": _Node("worker")},
    )
    initial = MultiAgentMessage("manager", "worker", "task", 0)
    retried = MultiAgentMessage("manager", "worker", "task", 0, delivery_attempt=1)
    assert retried.message_id == initial.message_id

    paused = coordinator.run(initial, max_rounds=4, max_messages=1)
    assert paused.status is MultiAgentRunStatus.MAX_MESSAGES
    assert paused.checkpoint is not None
    assert paused.checkpoint.delivered_messages == (initial,)
    resumed = coordinator.resume(paused.checkpoint, max_rounds=4, max_messages=10)
    assert resumed.status is MultiAgentRunStatus.COMPLETED
    assert tuple(message.turn for message in resumed.messages) == (0, 1, 2)


def test_group_chat_broadcasts_to_every_declared_neighbor() -> None:
    class Leaf:
        def __init__(self):
            self.received = []

        def handle(self, message):
            self.received.append(message)
            return ()

    leaves = {"alpha": Leaf(), "beta": Leaf()}
    topology = CommunicationTopology(
        ("moderator", "alpha", "beta"),
        (CommunicationEdge("moderator", "alpha"), CommunicationEdge("moderator", "beta")),
    )
    result = GroupChatCoordinator(
        MultiAgentCoordinator(topology, {"moderator": Leaf(), **leaves})
    ).run("moderator", "topic")
    assert result.status is MultiAgentRunStatus.COMPLETED
    assert {message.recipient for message in result.messages} == {"alpha", "beta"}
    assert len(leaves["alpha"].received) == len(leaves["beta"].received) == 1


def test_multi_agent_cancellation_leaves_a_resumable_checkpoint() -> None:
    class Cancelled:
        def cancelled(self):
            return True

    topology = CommunicationTopology(
        ("manager", "worker"), (CommunicationEdge("manager", "worker"),)
    )
    initial = MultiAgentMessage("manager", "worker", "task", 0)
    result = MultiAgentCoordinator(
        topology, {"manager": _Node("manager"), "worker": _Node("worker")}
    ).run(
        initial,
        cancellation=Cancelled(),
    )
    assert result.status is MultiAgentRunStatus.CANCELLED
    assert result.terminated is False
    assert result.checkpoint is not None
    assert result.checkpoint.pending == (initial,)
