from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from research_platform.platform.kernel import ExecutionContext

from ..api.contracts import MethodProgramIdentity
from ..api.graph import (
    MethodGraphCheckpointPort,
    MethodGraphEvent,
    MethodGraphRequest,
    MethodGraphResult,
)

TaskT = TypeVar("TaskT")
InputT = TypeVar("InputT")
ResumeT = TypeVar("ResumeT")
ResultT = TypeVar("ResultT")
EventT = TypeVar("EventT")


class LangGraphInvoker(Protocol):
    """Narrow public invoke surface; no LangGraph import is required here."""

    def invoke(
        self,
        input_value: object,
        *,
        config: Mapping[str, object],
        context: object,
        version: str,
    ) -> object: ...

    def stream(
        self,
        input_value: object,
        *,
        config: Mapping[str, object],
        context: object,
        version: str,
    ) -> Iterator[object]: ...


@dataclass(frozen=True, slots=True)
class LangGraphInvocation:
    input_value: object
    config: Mapping[str, object]
    context: object
    version: str = "v2"

    def __post_init__(self) -> None:
        if self.version not in ("v1", "v2"):
            raise ValueError("LangGraph invocation version must be v1 or v2")


class LangGraphCodec(Protocol[TaskT, InputT, ResumeT, ResultT, EventT]):
    """Provider adapter codec for typed Noetrium values and public graph values."""

    def encode(
        self, request: MethodGraphRequest[TaskT, InputT, ResumeT]
    ) -> LangGraphInvocation: ...

    def decode_result(self, raw: object) -> MethodGraphResult[ResultT]: ...

    def decode_event(self, raw: object) -> MethodGraphEvent[EventT]: ...
class LangGraphMethodProgram(
    Generic[TaskT, InputT, ResumeT, ResultT, EventT]
):
    """Host a LangGraph-compatible public graph as a Noetrium method program.

    The adapter owns translation only. ParticipantCheckpoint remains the outer
    binding/session/integrity authority; a graph checkpoint is opaque payload.
    """

    def __init__(
        self,
        *,
        program_identity: MethodProgramIdentity,
        graph: LangGraphInvoker,
        codec: LangGraphCodec[TaskT, InputT, ResumeT, ResultT, EventT],
    ) -> None:
        self._program_identity = program_identity
        self._graph = graph
        self._codec = codec

    @property
    def program_identity(self) -> MethodProgramIdentity:
        return self._program_identity

    def _request(
        self,
        *,
        task: TaskT,
        input_value: InputT,
        context: ExecutionContext,
        resume: ResumeT | None = None,
    ) -> MethodGraphRequest[TaskT, InputT, ResumeT]:
        session_id = context.lifetime_id or context.run_id
        invocation_id = context.operation_id or context.span_id
        return MethodGraphRequest(
            task=task,
            input_value=input_value,
            context=context,
            session_id=session_id,
            invocation_id=invocation_id,
            resume=resume,
        )

    def invoke(
        self, request: MethodGraphRequest[TaskT, InputT, ResumeT]
    ) -> MethodGraphResult[ResultT]:
        invocation = self._codec.encode(request)
        raw = self._graph.invoke(
            invocation.input_value,
            config=invocation.config,
            context=invocation.context,
            version=invocation.version,
        )
        return self._codec.decode_result(raw)

    def stream(
        self, request: MethodGraphRequest[TaskT, InputT, ResumeT]
    ) -> Iterator[MethodGraphEvent[EventT]]:
        invocation = self._codec.encode(request)
        previous_sequence = -1
        for raw in self._graph.stream(
            invocation.input_value,
            config=invocation.config,
            context=invocation.context,
            version=invocation.version,
        ):
            event = self._codec.decode_event(raw)
            if event.sequence <= previous_sequence:
                raise ValueError(
                    "LangGraph stream events must have strictly increasing sequence numbers"
                )
            previous_sequence = event.sequence
            yield event

    def run(
        self,
        *,
        task: TaskT,
        input_value: InputT,
        context: ExecutionContext,
    ) -> ResultT:
        return self.invoke(
            self._request(task=task, input_value=input_value, context=context)
        ).value

    def invoke_resumed(
        self,
        *,
        task: TaskT,
        input_value: InputT,
        resume: ResumeT,
        context: ExecutionContext,
    ) -> MethodGraphResult[ResultT]:
        return self.invoke(
            self._request(
                task=task,
                input_value=input_value,
                context=context,
                resume=resume,
            )
        )


class LangGraphStatefulMethodProgram(
    LangGraphMethodProgram[TaskT, InputT, ResumeT, ResultT, EventT]
):
    """Stateful adapter variant for a graph exposing the checkpoint capability."""

    def checkpoint_state(self) -> bytes:
        if not isinstance(self._graph, MethodGraphCheckpointPort):
            raise TypeError(
                "the configured graph does not expose the checkpoint capability"
            )
        return self._graph.checkpoint_state()

    def restore_state(self, payload: bytes) -> None:
        if not isinstance(self._graph, MethodGraphCheckpointPort):
            raise TypeError(
                "the configured graph does not expose the checkpoint capability"
            )
        self._graph.restore_state(payload)


__all__ = [
    "LangGraphCodec",
    "LangGraphInvocation",
    "LangGraphInvoker",
    "LangGraphMethodProgram",
    "LangGraphStatefulMethodProgram",
]
