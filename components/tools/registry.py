"""Typed local tool registry for agent methods.

The registry is explicitly constructed and injected into a method. It is not a
global provider locator and it never grants capabilities implicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable

from research_platform.platform.kernel import JsonValue, canonical_digest, freeze_json


@dataclass(frozen=True, slots=True)
class ToolArguments:
    values: tuple[tuple[str, JsonValue], ...] = ()

    @classmethod
    def from_mapping(cls, values: Mapping[str, JsonValue]) -> ToolArguments:
        if not isinstance(values, Mapping):
            raise TypeError("tool arguments must be a mapping")
        return cls(tuple(sorted((key, freeze_json(value)) for key, value in values.items())))

    def __post_init__(self) -> None:
        if type(self.values) is not tuple or any(type(row) is not tuple or len(row) != 2 for row in self.values):
            raise TypeError("tool argument values must be key/value tuples")
        keys = [row[0] for row in self.values]
        if any(type(key) is not str or not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("tool argument keys must be unique non-empty strings")

    def as_mapping(self) -> dict[str, JsonValue]:
        return dict(self.values)

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema_id: str
    definition_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (self.name, self.description, self.input_schema_id)):
            raise ValueError("tool definition fields must be non-empty strings")
        object.__setattr__(self, "definition_digest", canonical_digest({"name": self.name, "description": self.description, "input_schema_id": self.input_schema_id}))


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_name: str
    success: bool
    content: str
    error: str | None = None
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.tool_name) is not str or not self.tool_name.strip() or type(self.success) is not bool:
            raise TypeError("tool result identity/success are invalid")
        if type(self.content) is not str:
            raise TypeError("tool result content must be string")
        if self.error is not None and type(self.error) is not str:
            raise TypeError("tool result error must be string or None")
        if self.success and self.error is not None:
            raise ValueError("successful tool result cannot carry an error")
        object.__setattr__(self, "result_digest", canonical_digest({"tool_name": self.tool_name, "success": self.success, "content": self.content, "error": self.error}))


ToolHandler = Callable[[ToolArguments], ToolResult]


class ToolRegistry:
    """Explicit per-method registry with deterministic introspection."""

    def __init__(self) -> None:
        self._handlers: dict[str, tuple[ToolDefinition, ToolHandler]] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if type(definition) is not ToolDefinition or not callable(handler):
            raise TypeError("tool registry requires a ToolDefinition and callable handler")
        if definition.name in self._handlers:
            raise ValueError(f"tool already registered: {definition.name}")
        self._handlers[definition.name] = (definition, handler)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(row[0] for row in sorted(self._handlers.values(), key=lambda row: row[0].name))

    def invoke(self, name: str, arguments: ToolArguments) -> ToolResult:
        if type(name) is not str or not name.strip():
            raise ValueError("tool name must be non-empty")
        if type(arguments) is not ToolArguments:
            raise TypeError("tool invocation requires ToolArguments")
        entry = self._handlers.get(name)
        if entry is None:
            return ToolResult(name, False, "", f"unknown tool: {name}")
        try:
            result = entry[1](arguments)
        except Exception as exc:
            return ToolResult(name, False, "", f"{type(exc).__name__}: {exc}")
        if type(result) is not ToolResult or result.tool_name != name:
            raise RuntimeError("tool handler returned an invalid or foreign ToolResult")
        return result


__all__ = ["ToolArguments", "ToolDefinition", "ToolHandler", "ToolRegistry", "ToolResult"]
