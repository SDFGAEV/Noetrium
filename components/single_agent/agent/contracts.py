"""Typed contracts shared by reusable single-agent method components.

These components are method implementations, not Platform authorities. They
accept downstream policies, model clients, and tool ports through narrow seams.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from noetrium_platform.foundation.kernel.kernel import JsonValue, canonical_digest, freeze_json


class AgentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS = "max_steps"


class AgentActionKind(StrEnum):
    TOOL = "tool"
    FINAL = "final"
    CONTINUE = "continue"


@dataclass(frozen=True, slots=True)
class AgentMessage:
    role: str
    content: str
    name: str | None = None

    def __post_init__(self) -> None:
        if type(self.role) is not str or not self.role.strip():
            raise ValueError("agent message role must be non-empty")
        if type(self.content) is not str:
            raise TypeError("agent message content must be string")
        if self.name is not None and (type(self.name) is not str or not self.name.strip()):
            raise ValueError("agent message name must be non-empty when present")


@dataclass(frozen=True, slots=True)
class AgentState:
    task: str
    messages: tuple[AgentMessage, ...] = ()
    scratchpad: tuple[AgentMessage, ...] = ()
    step: int = 0

    def __post_init__(self) -> None:
        if type(self.task) is not str or not self.task.strip():
            raise ValueError("agent state task must be non-empty")
        if type(self.messages) is not tuple or any(type(row) is not AgentMessage for row in self.messages):
            raise TypeError("agent state messages must contain AgentMessage")
        if type(self.scratchpad) is not tuple or any(type(row) is not AgentMessage for row in self.scratchpad):
            raise TypeError("agent state scratchpad must contain AgentMessage")
        if type(self.step) is not int or isinstance(self.step, bool) or self.step < 0:
            raise ValueError("agent state step must be a non-negative integer")

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class AgentAction:
    kind: AgentActionKind
    name: str
    arguments: tuple[tuple[str, JsonValue], ...] = ()
    content: str = ""
    action_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AgentActionKind) or type(self.name) is not str or not self.name.strip():
            raise ValueError("agent action kind/name are invalid")
        if type(self.content) is not str:
            raise TypeError("agent action content must be string")
        if type(self.arguments) is not tuple or any(type(row) is not tuple or len(row) != 2 for row in self.arguments):
            raise TypeError("agent action arguments must be key/value tuples")
        keys = [row[0] for row in self.arguments]
        if any(type(key) is not str or not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("agent action argument keys must be unique non-empty strings")
        object.__setattr__(self, "action_digest", canonical_digest({"kind": self.kind.value, "name": self.name, "arguments": self.arguments, "content": self.content}))

    def argument_values(self) -> dict[str, JsonValue]:
        return {key: freeze_json(value) for key, value in self.arguments}


@dataclass(frozen=True, slots=True)
class AgentObservation:
    action_digest: str
    content: str
    success: bool
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.action_digest) is not str or len(self.action_digest) != 64:
            raise ValueError("agent observation action_digest must be SHA-256")
        if type(self.content) is not str or type(self.success) is not bool:
            raise TypeError("agent observation content/success types are invalid")
        object.__setattr__(self, "observation_digest", canonical_digest({"action_digest": self.action_digest, "content": self.content, "success": self.success}))


@dataclass(frozen=True, slots=True)
class AgentDecision:
    action: AgentAction
    reasoning: str = ""

    def __post_init__(self) -> None:
        if type(self.action) is not AgentAction or type(self.reasoning) is not str:
            raise TypeError("agent decision fields are invalid")
@dataclass(frozen=True, slots=True)
class AgentRunResult:
    status: AgentStatus
    answer: str | None
    state: AgentState
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AgentStatus) or type(self.state) is not AgentState:
            raise TypeError("agent run result fields are invalid")
        if self.answer is not None and type(self.answer) is not str:
            raise TypeError("agent run result answer must be string or None")
        if self.error is not None and type(self.error) is not str:
            raise TypeError("agent run result error must be string or None")
        if self.status is AgentStatus.COMPLETED and not self.answer:
            raise ValueError("completed agent run requires an answer")


class AgentDecisionPort(Protocol):
    def decide(self, state: AgentState) -> AgentDecision: ...


class AgentToolPort(Protocol):
    def invoke(self, name: str, arguments: tuple[tuple[str, JsonValue], ...]) -> AgentObservation: ...


class AgentReflectionPort(Protocol):
    def reflect(self, state: AgentState, result: AgentRunResult) -> AgentMessage: ...


class AgentPlannerPort(Protocol):
    def plan(self, task: str) -> tuple[str, ...]: ...


class AgentSolverPort(Protocol):
    def solve(self, task: str, plan: tuple[str, ...]) -> AgentRunResult: ...


__all__ = [
    "AgentAction", "AgentActionKind", "AgentDecision", "AgentDecisionPort",
    "AgentMessage", "AgentObservation", "AgentPlannerPort", "AgentReflectionPort",
    "AgentRunResult", "AgentSolverPort", "AgentState", "AgentStatus", "AgentToolPort",
]
