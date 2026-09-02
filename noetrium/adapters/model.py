"""Reference model adapters over the platform endpoint contract."""

from __future__ import annotations

from typing import Protocol

from components.reference.single_agent.agent import (
    ReferenceAgentDecision,
    ReferenceAgentState,
)
from noetrium.contracts.json import strict_json_loads
from noetrium_platform.capabilities.model.serving.endpoint.api import (
    ModelEndpointPort, ModelEndpointRequest,
)
from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from .bridges.adapters import normalize_foreign_decision


class ReferenceModelRequestFactoryPort(Protocol):
    def build(
        self, state: ReferenceAgentState, context: ExecutionContext
    ) -> ModelEndpointRequest: ...


class OpenAICompatibleDecisionAdapter:
    """Turn an OpenAI-compatible text endpoint into an agent decision port.

    Prompt construction, content-addressed request recording, and credentials
    stay in the injected request factory/endpoint.
    """

    def __init__(
        self,
        endpoint: ModelEndpointPort,
        request_factory: ReferenceModelRequestFactoryPort,
        context: ExecutionContext,
    ) -> None:
        if not callable(getattr(endpoint, "complete", None)):
            raise TypeError("model adapter endpoint must implement complete()")
        if not callable(getattr(request_factory, "build", None)):
            raise TypeError("model adapter request_factory must implement build()")
        if not isinstance(context, ExecutionContext):
            raise TypeError("model adapter context must be an ExecutionContext")
        self._endpoint = endpoint
        self._request_factory = request_factory
        self._context = context

    def decide(self, state: ReferenceAgentState) -> ReferenceAgentDecision:
        response = self._endpoint.complete(
            self._request_factory.build(state, self._context)
        )
        text = response.text.strip()
        if text.startswith("{"):
            try:
                return normalize_foreign_decision(strict_json_loads(text))
            except (TypeError, ValueError):
                pass
        return normalize_foreign_decision(text)


__all__ = [
    "OpenAICompatibleDecisionAdapter", "ReferenceModelRequestFactoryPort",
]
