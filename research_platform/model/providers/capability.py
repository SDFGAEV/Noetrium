from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from research_platform.model.api import (
    ModelCapabilityInput,
    ModelCapabilityInvocation,
    ModelCapabilityOutput,
    ModelCapabilityRequirement,
    ModelCapabilityResponse,
    ProjectModelBinding,
)

InputT = TypeVar("InputT", bound=ModelCapabilityInput)
OutputT = TypeVar("OutputT", bound=ModelCapabilityOutput)


@dataclass(frozen=True, slots=True)
class FunctionalModelCapabilityClient(Generic[InputT, OutputT]):
    requirement: ModelCapabilityRequirement
    binding: ProjectModelBinding
    _handler: Callable[[InputT], OutputT]

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, ModelCapabilityRequirement):
            raise TypeError("functional capability requirement must be typed")
        if not isinstance(self.binding, ProjectModelBinding):
            raise TypeError("functional capability binding must be typed")
        if self.binding.requirement_digest != self.requirement.digest():
            raise ValueError("functional capability binding requirement provenance drift")
        if self.binding.capability_id != self.requirement.capability_id:
            raise ValueError("functional capability binding capability provenance drift")
        if self.binding.input_schema_id != self.requirement.input_schema_id:
            raise ValueError("functional capability binding input schema drift")
        if self.binding.output_schema_id != self.requirement.output_schema_id:
            raise ValueError("functional capability binding output schema drift")
        if not callable(self._handler):
            raise TypeError("functional capability handler must be callable")

    def invoke(
        self, request: ModelCapabilityInvocation[InputT]
    ) -> ModelCapabilityResponse[OutputT]:
        if not isinstance(request, ModelCapabilityInvocation):
            raise TypeError("functional capability request must be typed")
        if request.requirement_digest != self.requirement.digest():
            raise ValueError("functional capability request requirement provenance drift")
        if request.capability_id != self.requirement.capability_id:
            raise ValueError("functional capability request capability drift")
        if request.input_schema_id != self.requirement.input_schema_id:
            raise ValueError("functional capability request input schema drift")
        output = self._handler(request.payload)
        if not isinstance(output, ModelCapabilityOutput):
            raise TypeError("functional capability handler returned an untyped output")
        if output.schema_id != self.requirement.output_schema_id:
            raise ValueError("functional capability handler output schema drift")
        return ModelCapabilityResponse(
            request_digest=request.request_digest,
            binding_digest=self.binding.digest(),
            output_schema_id=self.requirement.output_schema_id,
            output=output,
        )


@dataclass(frozen=True, slots=True)
class FunctionalModelCapabilityProvider(Generic[InputT, OutputT]):
    capability_id: str
    _binding_factory: Callable[[ModelCapabilityRequirement], ProjectModelBinding]
    _handler: Callable[[InputT], OutputT]

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("functional capability_id must be non-empty")
        if not callable(self._binding_factory):
            raise TypeError("functional capability binding factory must be callable")
        if not callable(self._handler):
            raise TypeError("functional capability handler must be callable")

    def bind_capability(
        self, requirement: ModelCapabilityRequirement
    ) -> FunctionalModelCapabilityClient[InputT, OutputT]:
        if not isinstance(requirement, ModelCapabilityRequirement):
            raise TypeError("functional capability requirement must be typed")
        if requirement.capability_id != self.capability_id:
            raise ValueError("functional capability provider does not own requested capability")
        binding = self._binding_factory(requirement)
        if not isinstance(binding, ProjectModelBinding):
            raise TypeError("functional capability binding factory returned an untyped binding")
        return FunctionalModelCapabilityClient(
            requirement=requirement,
            binding=binding,
            _handler=self._handler,
        )


__all__ = [
    "FunctionalModelCapabilityClient",
    "FunctionalModelCapabilityProvider",
]
