from __future__ import annotations

from noetrium_platform.foundation.kernel.kernel import JsonValue

from components.single_agent.tools import ToolArguments, ToolRegistry
from .contracts import AgentObservation


class RegistryAgentToolPort:
    """Adapter from the reusable ToolRegistry to the ReAct tool port."""

    def __init__(self, registry: ToolRegistry) -> None:
        if type(registry) is not ToolRegistry:
            raise TypeError("registry tool port requires ToolRegistry")
        self._registry = registry

    def invoke(
        self, name: str, arguments: tuple[tuple[str, JsonValue], ...]
    ) -> AgentObservation:
        result = self._registry.invoke(name, ToolArguments(arguments))
        return AgentObservation(
            result.result_digest,
            result.error or result.content,
            result.success,
        )


__all__ = ["RegistryAgentToolPort"]
