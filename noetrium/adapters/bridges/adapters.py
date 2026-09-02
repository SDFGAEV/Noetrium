"""Dependency-free bridges for foreign agent runtimes.

Foreign state and decisions are normalized at this boundary. LangGraph,
AutoGen, and CrewAI remain optional dependencies; Noetrium owns the typed
method contract, action identity, and tool/capability authorization.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from noetrium.contracts.json import JsonValue, strict_json_loads
from components.reference.single_agent.agent import (
    ReferenceAgentAction,
    ReferenceAgentActionKind,
    ReferenceAgentDecision,
    ReferenceAgentDecisionPort,
    ReferenceAgentObservation,
    ReferenceAgentState,
    ReferenceAgentToolPort,
)


class LangGraphRunnable(Protocol):
    def invoke(self, state: object) -> object: ...


class AutoGenRunnable(Protocol):
    def run(self, state: object) -> object: ...


class CrewAIRunnable(Protocol):
    def kickoff(self, state: object) -> object: ...


class ForeignStateConverterPort(Protocol):
    def convert(self, state: ReferenceAgentState) -> object: ...


class ForeignDecisionConverterPort(Protocol):
    def convert(self, decision: object) -> ReferenceAgentDecision: ...


def reference_state_mapping(state: ReferenceAgentState) -> dict[str, object]:
    return {
        "task": state.task,
        "messages": tuple({
            "role": row.role, "content": row.content, "name": row.name,
        } for row in state.messages),
        "scratchpad": tuple({
            "role": row.role, "content": row.content, "name": row.name,
        } for row in state.scratchpad),
        "step": state.step,
    }


def _action_from_mapping(value: Mapping[str, JsonValue]) -> ReferenceAgentAction:
    nested = value.get("action")
    raw = nested if isinstance(nested, Mapping) else value
    raw_kind = raw.get("kind", raw.get("type", "final"))
    if isinstance(raw_kind, str):
        try:
            kind = ReferenceAgentActionKind(raw_kind.lower())
        except ValueError as exc:
            raise TypeError(f"foreign action kind is unsupported: {raw_kind}") from exc
    else:
        raise TypeError("foreign action kind must be text")
    name = raw.get("name", raw.get("tool_name", "final"))
    if not isinstance(name, str):
        raise TypeError("foreign action name must be text")
    arguments = raw.get("arguments", raw.get("args", {}))
    if arguments is None:
        arguments = {}
    if isinstance(arguments, Mapping):
        normalized = dict(arguments)
    elif isinstance(arguments, (list, tuple)):
        normalized = dict(arguments)
    else:
        raise TypeError("foreign action arguments must be a mapping")
    content = raw.get("content", raw.get("text", ""))
    if not isinstance(content, str):
        raise TypeError("foreign action content must be text")
    return ReferenceAgentAction.from_mapping(kind, name, normalized, content=content)


def _normalize_tool_call(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    function = value.get("function")
    if isinstance(function, Mapping):
        name = function.get("name", value.get("name"))
        arguments = function.get("arguments", value.get("arguments", value.get("args", {})))
    else:
        name = value.get("name")
        arguments = value.get("arguments", value.get("args", {}))
    if not isinstance(name, str) or not name.strip():
        raise TypeError("foreign tool call name must be non-empty")
    if isinstance(arguments, str):
        arguments = strict_json_loads(arguments)
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, Mapping):
        raise TypeError("foreign tool call arguments must be a mapping")
    return {"name": name, "arguments": dict(arguments)}


def normalize_foreign_decision(value: object) -> ReferenceAgentDecision:
    if type(value) is ReferenceAgentDecision:
        return value
    if isinstance(value, str):
        return ReferenceAgentDecision(
            ReferenceAgentAction(ReferenceAgentActionKind.FINAL, "final", content=value)
        )
    if not isinstance(value, Mapping):
        raw_tool_calls = getattr(value, "tool_calls", None)
        raw_content = getattr(value, "content", None)
        if isinstance(raw_tool_calls, (list, tuple)) or isinstance(raw_content, str):
            value = {"tool_calls": raw_tool_calls or (), "content": raw_content or ""}
        else:
            raise TypeError("foreign runtime decision must be a mapping, string, or ReferenceAgentDecision")
    candidate = value.get("decision", value)
    if isinstance(candidate, Mapping):
        messages = candidate.get("messages")
        if isinstance(messages, (list, tuple)) and messages and isinstance(messages[-1], Mapping):
            last = messages[-1]
            if "tool_calls" in last or "content" in last:
                candidate = last
        tool_calls = candidate.get("tool_calls")
        if isinstance(tool_calls, (list, tuple)) and tool_calls:
            call = tool_calls[0]
            if isinstance(call, Mapping):
                normalized_call = _normalize_tool_call(call)
                candidate = {
                    "kind": "tool", "name": normalized_call["name"],
                    "arguments": normalized_call["arguments"],
                    "content": candidate.get("content", ""),
                }
        return ReferenceAgentDecision(
            _action_from_mapping(candidate),
            str(value.get("reasoning", value.get("thought", ""))),
        )
    raise TypeError("foreign runtime decision field is malformed")


def _decision(
    runnable: object,
    state: ReferenceAgentState,
    method: str,
    state_converter: ForeignStateConverterPort | None,
    decision_converter: ForeignDecisionConverterPort | None,
) -> ReferenceAgentDecision:
    target = state if state_converter is None else state_converter.convert(state)
    result = getattr(runnable, method)(target)
    return (
        normalize_foreign_decision(result)
        if decision_converter is None
        else decision_converter.convert(result)
    )


class LangGraphDecisionAdapter(ReferenceAgentDecisionPort):
    def __init__(
        self,
        runnable: LangGraphRunnable,
        *,
        state_converter: ForeignStateConverterPort | None = None,
        decision_converter: ForeignDecisionConverterPort | None = None,
    ) -> None:
        self._runnable = runnable
        self._state_converter = state_converter
        self._decision_converter = decision_converter

    def decide(self, state: ReferenceAgentState) -> ReferenceAgentDecision:
        return _decision(self._runnable, state, "invoke", self._state_converter, self._decision_converter)


class AutoGenDecisionAdapter(ReferenceAgentDecisionPort):
    def __init__(
        self,
        runnable: AutoGenRunnable,
        *,
        state_converter: ForeignStateConverterPort | None = None,
        decision_converter: ForeignDecisionConverterPort | None = None,
    ) -> None:
        self._runnable = runnable
        self._state_converter = state_converter
        self._decision_converter = decision_converter

    def decide(self, state: ReferenceAgentState) -> ReferenceAgentDecision:
        return _decision(self._runnable, state, "run", self._state_converter, self._decision_converter)


class CrewAIDecisionAdapter(ReferenceAgentDecisionPort):
    def __init__(
        self,
        runnable: CrewAIRunnable,
        *,
        state_converter: ForeignStateConverterPort | None = None,
        decision_converter: ForeignDecisionConverterPort | None = None,
    ) -> None:
        self._runnable = runnable
        self._state_converter = state_converter
        self._decision_converter = decision_converter

    def decide(self, state: ReferenceAgentState) -> ReferenceAgentDecision:
        return _decision(self._runnable, state, "kickoff", self._state_converter, self._decision_converter)


class LangGraphToolNodeAdapter:
    """Normalize a ToolNode-style call into a reference tool invocation."""

    def __init__(self, tools: ReferenceAgentToolPort) -> None:
        self._tools = tools

    def invoke(self, tool_call: Mapping[str, JsonValue]) -> ReferenceAgentObservation:
        normalized_call = _normalize_tool_call(tool_call)
        name = normalized_call["name"]
        arguments = normalized_call["arguments"]
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            raise TypeError("normalized foreign tool call is malformed")
        action = ReferenceAgentAction.from_mapping(
            ReferenceAgentActionKind.TOOL, name, arguments,
        )
        invoke_action = getattr(self._tools, "invoke_action", None)
        return (
            invoke_action(action)
            if callable(invoke_action)
            else self._tools.invoke(action.name, action.arguments)
        )


__all__ = [
    "AutoGenDecisionAdapter", "AutoGenRunnable", "CrewAIDecisionAdapter",
    "CrewAIRunnable", "ForeignDecisionConverterPort", "ForeignStateConverterPort",
    "LangGraphDecisionAdapter", "LangGraphRunnable", "LangGraphToolNodeAdapter",
    "normalize_foreign_decision", "reference_state_mapping",
]
