from __future__ import annotations

from noetrium.contracts.json import JsonValue

from noetrium.components.reference.single_agent.tools import ToolArguments, ToolRegistry
from .contracts import ReferenceAgentObservation


class ReferenceToolRegistryPort:
    """Adapter from the reusable ToolRegistry to the ReAct tool port."""

    def __init__(self, registry: ToolRegistry) -> None:
        if type(registry) is not ToolRegistry:
            raise TypeError("registry tool port requires ToolRegistry")
        self._registry = registry

    def invoke(
        self, name: str, arguments: tuple[tuple[str, JsonValue], ...]
    ) -> ReferenceAgentObservation:
        result = self._registry.invoke(name, ToolArguments(arguments))
        return ReferenceAgentObservation(
            result.result_digest,
            result.error or result.content,
            result.success,
        )


__all__ = ["ReferenceToolRegistryPort"]
