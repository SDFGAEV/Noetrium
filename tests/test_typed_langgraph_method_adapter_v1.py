from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from noetrium_platform.capabilities.participant.method.api import (
    MethodGraphEvent,
    MethodGraphRequest,
    MethodGraphResult,
    MethodIdentity,
    MethodProgramIdentity,
    MethodGraphProgram,
    ResearchMethodProgram,
    StatefulResearchMethodProgram,
)
from noetrium_platform.capabilities.participant.method.providers import (
    LangGraphAsyncInvoker,
    LangGraphCodec,
    LangGraphInvocation,
    LangGraphMethodProgram,
    LangGraphStatefulMethodProgram,
)
from noetrium_platform.foundation.kernel.kernel import ExecutionContext


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str


@dataclass(frozen=True, slots=True)
class Input:
    prompt: str


@dataclass(frozen=True, slots=True)
class FakeGraph:
    """A public-API-shaped fake; the test never installs LangGraph."""

    calls: tuple[tuple[object, object, object, str], ...] = ()
    state: bytes = b"0"

    def invoke(
        self, input_value: object, *, config: dict[str, object],
        context: object, version: str,
    ) -> object:
        call = (input_value, config, context, version)
        object.__setattr__(self, "calls", self.calls + (call,))
        return {"value": "done", "interrupts": ()}

    def stream(
        self, input_value: object, *, config: dict[str, object],
        context: object, version: str,
    ):
        yield {"sequence": 0, "kind": "values", "node": "answer", "payload": "done"}
    def checkpoint_state(self) -> bytes:
        return self.state

    def restore_state(self, payload: bytes) -> None:
        object.__setattr__(self, "state", bytes(payload))


@dataclass(frozen=True, slots=True)
class AsyncGraph:
    async def ainvoke(
        self, input_value: object, *, config: dict[str, object],
        context: object, version: str,
    ) -> object:
        return {"value": "done", "interrupts": ()}

    async def astream(
        self, input_value: object, *, config: dict[str, object],
        context: object, version: str,
    ):
        yield {
            "sequence": 0, "kind": "updates", "node": "answer",
            "payload": "done",
        }


class Codec(LangGraphCodec[Task, Input, str, str, str]):
    def encode(
        self, request: MethodGraphRequest[Task, Input, str]
    ) -> LangGraphInvocation:
        return LangGraphInvocation(
            input_value={
                "task_id": request.task.task_id,
                "prompt": request.input_value.prompt,
                "resume": request.resume,
            },
            config={
                "configurable": {"thread_id": request.session_id},
                "invocation_id": request.invocation_id,
            },
            context=request.context,
        )

    def decode_result(self, raw: object) -> MethodGraphResult[str]:
        assert isinstance(raw, dict)
        assert raw["value"] == "done"
        return MethodGraphResult("done")

    def decode_event(self, raw: object) -> MethodGraphEvent[str]:
        assert isinstance(raw, dict)
        return MethodGraphEvent(
            sequence=raw["sequence"],
            kind=raw["kind"],
            node=raw["node"],
            payload=raw["payload"],
        )


def _program(stateful: bool = False, graph: object | None = None):
    graph = graph or FakeGraph()
    program_type = LangGraphStatefulMethodProgram if stateful else LangGraphMethodProgram
    program = program_type(
        program_identity=MethodProgramIdentity(
            MethodIdentity("langgraph-paper", "1", "abi1", "schema1", "a" * 64),
            "b" * 64,
        ),
        graph=graph,
        codec=Codec(),
    )
    return program, graph


def _context() -> ExecutionContext:
    return ExecutionContext(
        "run-1", "trace-1", "span-1",
        lifetime_id="session-1", operation_id="op-1",
    )


def test_langgraph_adapter_is_a_typed_whole_method_and_graph_program():
    program, graph = _program()

    assert isinstance(program, ResearchMethodProgram)
    assert isinstance(program, MethodGraphProgram)
    assert not isinstance(program, StatefulResearchMethodProgram)
    assert program.run(
        task=Task("task-1"), input_value=Input("hello"), context=_context()
    ) == "done"
    assert graph.calls[0][0] == {
        "task_id": "task-1", "prompt": "hello", "resume": None,
    }
    assert graph.calls[0][1]["configurable"] == {"thread_id": "session-1"}


def test_langgraph_adapter_keeps_resume_and_stream_as_explicit_typed_boundaries():
    program, graph = _program()
    request = MethodGraphRequest(
        Task("task-2"), Input("review"), _context(), "session-1", "op-2", "approve"
    )

    result = program.invoke(request)
    events = tuple(program.stream(request))

    assert result == MethodGraphResult("done")
    assert events == (MethodGraphEvent(0, "values", "answer", "done"),)
    assert graph.calls[0][0]["resume"] == "approve"


def test_langgraph_async_adapter_keeps_async_graphs_optional_and_typed():
    graph = AsyncGraph()
    program, _ = _program(graph=graph)
    request = MethodGraphRequest(
        Task("task-async"), Input("review"), _context(),
        "session-1", "op-async", None,
    )

    async def exercise():
        result = await program.ainvoke(request)
        events = tuple([event async for event in program.astream(request)])
        return result, events

    result, events = asyncio.run(exercise())
    assert isinstance(graph, LangGraphAsyncInvoker)
    assert result == MethodGraphResult("done")
    assert events == (MethodGraphEvent(0, "updates", "answer", "done"),)


def test_langgraph_checkpoint_capability_is_delegated_without_new_platform_identity():
    program, graph = _program(True)

    assert isinstance(program, StatefulResearchMethodProgram)
    assert program.checkpoint_state() == b"0"
    program.restore_state(b"7")
    assert graph.state == b"7"


def test_langgraph_adapter_fails_explicitly_when_checkpoint_is_not_supported():
    program, _ = _program()
    # Replace the graph with an invoke-only object through the private constructor
    # seam; production callers receive the same clear capability error.
    invoke_only = type(
        "InvokeOnly",
        (),
        {"invoke": lambda self, input_value, *, config, context, version: {}},
    )()
    program = LangGraphStatefulMethodProgram(
        program_identity=program.program_identity,
        graph=invoke_only,
        codec=Codec(),
    )

    try:
        program.checkpoint_state()
    except TypeError as exc:
        assert "checkpoint capability" in str(exc)
    else:
        raise AssertionError("missing checkpoint capability was accepted")


def test_langgraph_provider_has_no_hard_runtime_import():
    source = (
        Path(__file__).parents[1]
        / "noetrium_platform/capabilities/participant/method/providers/langgraph.py"
    ).read_text(encoding="utf-8")
    assert "import langgraph" not in source
