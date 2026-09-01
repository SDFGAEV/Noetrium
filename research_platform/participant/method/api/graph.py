from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from research_platform.platform.kernel import ExecutionContext

from .contracts import MethodProgramIdentity

TaskT = TypeVar("TaskT")
InputT = TypeVar("InputT")
ResumeT = TypeVar("ResumeT")
ResultT = TypeVar("ResultT")
EventT = TypeVar("EventT")


@dataclass(frozen=True, slots=True)
class MethodGraphRequest(Generic[TaskT, InputT, ResumeT]):
    task: TaskT
    input_value: InputT
    context: ExecutionContext
    session_id: str
    invocation_id: str
    resume: ResumeT | None = None

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.session_id, self.invocation_id,
        )):
            raise ValueError("method graph request identity fields are required")


@dataclass(frozen=True, slots=True)
class MethodGraphInterrupt:
    interrupt_id: str
    node: str
    payload: object

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.interrupt_id, self.node,
        )):
            raise ValueError("method graph interrupt identity fields are required")
@dataclass(frozen=True, slots=True)
class MethodGraphResult(Generic[ResultT]):
    value: ResultT
    interrupts: tuple[MethodGraphInterrupt, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodGraphEvent(Generic[EventT]):
    sequence: int
    kind: str
    node: str
    payload: EventT
    checkpoint_id: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("method graph event sequence must be non-negative")
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.kind, self.node,
        )):
            raise ValueError("method graph event kind and node are required")


@runtime_checkable
class MethodGraphProgram(Protocol[TaskT, InputT, ResultT, ResumeT, EventT]):
    """Framework-neutral, resumable graph surface for downstream paper methods."""

    @property
    def program_identity(self) -> MethodProgramIdentity: ...

    def invoke(
        self, request: MethodGraphRequest[TaskT, InputT, ResumeT]
    ) -> MethodGraphResult[ResultT]: ...

    def stream(
        self, request: MethodGraphRequest[TaskT, InputT, ResumeT]
    ) -> Iterator[MethodGraphEvent[EventT]]: ...
@runtime_checkable
class MethodGraphCheckpointPort(Protocol):
    """Optional graph-state trait; the participant envelope remains authoritative."""

    def checkpoint_state(self) -> bytes: ...

    def restore_state(self, payload: bytes) -> None: ...


__all__ = [
    "MethodGraphCheckpointPort",
    "MethodGraphEvent",
    "MethodGraphInterrupt",
    "MethodGraphProgram",
    "MethodGraphRequest",
    "MethodGraphResult",
]