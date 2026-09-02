from __future__ import annotations

from components.single_agent.agent import (
    AgentAction,
    AgentActionKind,
    AgentDecision,
    AgentMessage,
    AgentStatus,
    ReActAgent,
    RegistryAgentToolPort,
)
from components.single_agent.memory import MemoryItem, VectorMemoryStore, WorkingMemory
from components.orchestration.multi_agent import (
    CommunicationEdge,
    CommunicationTopology,
    MultiAgentCoordinator,
    MultiAgentMessage,
)
from components.single_agent.tools import ToolArguments, ToolDefinition, ToolRegistry, ToolResult


class _Policy:
    def decide(self, state):
        if state.step == 0:
            return AgentDecision(
                AgentAction(
                    AgentActionKind.TOOL,
                    "echo",
                    (("value", "observed"),),
                    "use echo",
                )
            )
        return AgentDecision(AgentAction(AgentActionKind.FINAL, "answer", content="done"))


def test_react_is_importable_and_tool_registry_is_explicit() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("echo", "return text", "tool.echo.v1"),
        lambda arguments: ToolResult("echo", True, arguments.as_mapping()["value"]),
    )
    result = ReActAgent(_Policy(), RegistryAgentToolPort(registry)).run("task", max_steps=3)
    assert result.status is AgentStatus.COMPLETED
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
        return (MultiAgentMessage(self.name, target, f"reply:{message.content}", message.turn + 1),)


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
    from components.single_agent.memory import EpisodicMemoryStore

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
