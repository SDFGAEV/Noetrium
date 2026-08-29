from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from research_platform.model.request.api import ModelRequestEnvelope
from research_platform.model.request._immutable_json import freeze_json_object
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity, JsonObject


@dataclass(frozen=True, slots=True)
class PromptDynamicBlock:
    """Project-owned dynamic evidence expressed in the prompt API vocabulary."""

    kind: str
    content: str
    source_digest: str
    sequence: int


@dataclass(frozen=True, slots=True)
class PromptBodyContext:
    """Compiled prompt facts exposed to a project body-shaping function."""

    prompt_id: str
    prompt_digest: str
    role: str
    model_id: str
    output_schema: str
    compiled_text: str
    temperature: float
    top_p: float
    max_output_tokens: int


PromptRequestBodyBuilder = Callable[[PromptBodyContext], JsonObject]


@dataclass(frozen=True, slots=True)
class PromptBoundRequest:
    request: ModelRequestEnvelope
    body: JsonObject
    prompt_generation_id: str
    prompt_id: str
    prompt_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", freeze_json_object(self.body, field="prompt-bound request body"))


class PromptRequestBindingPort(Protocol):
    """Frozen prompt-to-model-request port consumed by project composition."""

    def build(
        self,
        *,
        blocks: tuple[PromptDynamicBlock, ...],
        context_length: int,
        request_id: str,
        context: ExecutionContext,
        model: ImmutableModelIdentity,
        body_builder: PromptRequestBodyBuilder,
        source_artifact_refs: tuple[str, ...] = (),
        source_state_refs: tuple[str, ...] = (),
    ) -> PromptBoundRequest: ...


__all__ = [
    "PromptBoundRequest",
    "PromptBodyContext",
    "PromptDynamicBlock",
    "PromptRequestBindingPort",
    "PromptRequestBodyBuilder",
]
