from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, runtime_checkable

from research_platform.model.api.project import (
    ModelCapabilityRequirement,
    ProjectModelBinding,
)
from research_platform.platform.kernel import canonical_digest


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value


def _sha256(value: object, field_name: str) -> str:
    digest = _text(value, field_name)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return digest


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result

@runtime_checkable
class ModelCapabilityInput(Protocol):
    @property
    def schema_id(self) -> str: ...

    def digest(self) -> str: ...


@runtime_checkable
class ModelCapabilityOutput(Protocol):
    @property
    def schema_id(self) -> str: ...

    def digest(self) -> str: ...


InputT = TypeVar("InputT", bound=ModelCapabilityInput)
OutputT = TypeVar("OutputT", bound=ModelCapabilityOutput)


@dataclass(frozen=True, slots=True)
class ModelCapabilityInvocation(Generic[InputT]):
    requirement_digest: str
    capability_id: str
    input_schema_id: str
    invocation_id: str
    payload: InputT
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha256(self.requirement_digest, "model capability invocation requirement_digest")
        _text(self.capability_id, "model capability invocation capability_id")
        _text(self.input_schema_id, "model capability invocation input_schema_id")
        _text(self.invocation_id, "model capability invocation invocation_id")
        if not isinstance(self.payload, ModelCapabilityInput):
            raise TypeError("model capability payload must implement ModelCapabilityInput")
        if self.payload.schema_id != self.input_schema_id:
            raise ValueError("model capability input schema does not match invocation schema")
        object.__setattr__(
            self,
            "request_digest",
            canonical_digest(
                {
                    "requirement_digest": self.requirement_digest,
                    "capability_id": self.capability_id,
                    "input_schema_id": self.input_schema_id,
                    "invocation_id": self.invocation_id,
                    "payload_digest": self.payload.digest(),
                }
            ),
        )

    @classmethod
    def from_requirement(
        cls,
        requirement: ModelCapabilityRequirement,
        invocation_id: str,
        payload: InputT,
    ) -> "ModelCapabilityInvocation[InputT]":
        if not isinstance(requirement, ModelCapabilityRequirement):
            raise TypeError("model capability requirement must be typed")
        if payload.schema_id != requirement.input_schema_id:
            raise ValueError("model capability input schema does not satisfy requirement")
        return cls(
            requirement_digest=requirement.digest(),
            capability_id=requirement.capability_id,
            input_schema_id=requirement.input_schema_id,
            invocation_id=invocation_id,
            payload=payload,
        )


@dataclass(frozen=True, slots=True)
class ModelCapabilityResponse(Generic[OutputT]):
    request_digest: str
    binding_digest: str
    output_schema_id: str
    output: OutputT
    response_digest: str = field(init=False)
    def __post_init__(self) -> None:
        _sha256(self.request_digest, "model capability response request_digest")
        _sha256(self.binding_digest, "model capability response binding_digest")
        _text(self.output_schema_id, "model capability response output_schema_id")
        if not isinstance(self.output, ModelCapabilityOutput):
            raise TypeError("model capability output must implement ModelCapabilityOutput")
        if self.output.schema_id != self.output_schema_id:
            raise ValueError("model capability output schema does not match response schema")
        object.__setattr__(
            self,
            "response_digest",
            canonical_digest({
                "request_digest": self.request_digest,
                "binding_digest": self.binding_digest,
                "output_schema_id": self.output_schema_id,
                "output_digest": self.output.digest(),
            }),
        )


@runtime_checkable
class ProjectModelCapabilityClientPort(Protocol[InputT, OutputT]):
    @property
    def binding(self) -> ProjectModelBinding: ...

    @property
    def requirement(self) -> ModelCapabilityRequirement: ...

    def invoke(
        self, request: ModelCapabilityInvocation[InputT]
    ) -> ModelCapabilityResponse[OutputT]: ...


@runtime_checkable
class ProjectModelCapabilityProviderPort(Protocol[InputT, OutputT]):
    @property
    def capability_id(self) -> str: ...

    def bind_capability(
        self, requirement: ModelCapabilityRequirement
    ) -> ProjectModelCapabilityClientPort[InputT, OutputT]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    texts: tuple[str, ...]
    normalize: bool = False
    schema_id: str = field(init=False, default="model.embedding.input.v1")

    def __post_init__(self) -> None:
        if not isinstance(self.texts, tuple) or not self.texts:
            raise TypeError("embedding texts must be a non-empty tuple")
        if any(not isinstance(text, str) or not text for text in self.texts):
            raise ValueError("embedding texts must contain non-empty strings")
        if type(self.normalize) is not bool:
            raise TypeError("embedding normalize must be bool")

    def digest(self) -> str:
        return canonical_digest(self)

@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple) or not self.values:
            raise TypeError("embedding vector must be a non-empty tuple")
        normalized = tuple(_finite(value, "embedding vector value") for value in self.values)
        object.__setattr__(self, "values", normalized)


@dataclass(frozen=True, slots=True)
class EmbeddingOutput:
    vectors: tuple[EmbeddingVector, ...]
    model_revision: str
    schema_id: str = field(init=False, default="model.embedding.output.v1")

    def __post_init__(self) -> None:
        if not isinstance(self.vectors, tuple) or not self.vectors:
            raise TypeError("embedding output vectors must be a non-empty tuple")
        if any(not isinstance(vector, EmbeddingVector) for vector in self.vectors):
            raise TypeError("embedding output vectors must be typed EmbeddingVector values")
        dimensions = {len(vector.values) for vector in self.vectors}
        if len(dimensions) != 1:
            raise ValueError("embedding output vectors must share one dimension")
        _text(self.model_revision, "embedding output model_revision")

    def digest(self) -> str:
        return canonical_digest(self)

@dataclass(frozen=True, slots=True)
class ScoringCandidate:
    candidate_id: str
    text: str

    def __post_init__(self) -> None:
        _text(self.candidate_id, "scoring candidate_id")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("scoring candidate text must be non-empty")


@dataclass(frozen=True, slots=True)
class ScoringInput:
    query: str
    candidates: tuple[ScoringCandidate, ...]
    schema_id: str = field(init=False, default="model.scoring.input.v1")

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query:
            raise ValueError("scoring query must be non-empty")
        if not isinstance(self.candidates, tuple) or not self.candidates:
            raise TypeError("scoring candidates must be a non-empty tuple")
        if any(not isinstance(candidate, ScoringCandidate) for candidate in self.candidates):
            raise TypeError("scoring candidates must be typed ScoringCandidate values")
        ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("scoring candidate ids must be unique")

    def digest(self) -> str:
        return canonical_digest(self)

@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate_id: str
    score: float

    def __post_init__(self) -> None:
        _text(self.candidate_id, "scored candidate_id")
        object.__setattr__(self, "score", _finite(self.score, "scored candidate score"))


@dataclass(frozen=True, slots=True)
class ScoringOutput:
    scores: tuple[ScoredCandidate, ...]
    model_revision: str
    higher_is_better: bool = True
    schema_id: str = field(init=False, default="model.scoring.output.v1")

    def __post_init__(self) -> None:
        if not isinstance(self.scores, tuple) or not self.scores:
            raise TypeError("scoring output scores must be a non-empty tuple")
        if any(not isinstance(score, ScoredCandidate) for score in self.scores):
            raise TypeError("scoring output scores must be typed ScoredCandidate values")
        ids = tuple(score.candidate_id for score in self.scores)
        if len(ids) != len(set(ids)):
            raise ValueError("scoring output candidate ids must be unique")
        _text(self.model_revision, "scoring output model_revision")
        if type(self.higher_is_better) is not bool:
            raise TypeError("scoring higher_is_better must be bool")

    def digest(self) -> str:
        return canonical_digest(self)

@dataclass(frozen=True, slots=True)
class NamedScalar:
    name: str
    value: float

    def __post_init__(self) -> None:
        _text(self.name, "named scalar name")
        object.__setattr__(self, "value", _finite(self.value, "named scalar value"))


@dataclass(frozen=True, slots=True)
class ValueInferenceInput:
    features: tuple[NamedScalar, ...]
    state_id: str | None = None
    schema_id: str = field(init=False, default="model.value.input.v1")

    def __post_init__(self) -> None:
        if not isinstance(self.features, tuple) or not self.features:
            raise TypeError("value inference features must be a non-empty tuple")
        if any(not isinstance(feature, NamedScalar) for feature in self.features):
            raise TypeError("value inference features must be typed NamedScalar values")
        names = tuple(feature.name for feature in self.features)
        if len(names) != len(set(names)):
            raise ValueError("value inference feature names must be unique")
        if self.state_id is not None:
            _text(self.state_id, "value inference state_id")

    def digest(self) -> str:
        return canonical_digest(self)

@dataclass(frozen=True, slots=True)
class ValueInferenceOutput:
    value: float
    model_revision: str
    uncertainty: float | None = None
    schema_id: str = field(init=False, default="model.value.output.v1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _finite(self.value, "value inference value"))
        _text(self.model_revision, "value inference model_revision")
        if self.uncertainty is not None:
            uncertainty = _finite(self.uncertainty, "value inference uncertainty")
            if uncertainty < 0:
                raise ValueError("value inference uncertainty must be non-negative")
            object.__setattr__(self, "uncertainty", uncertainty)

    def digest(self) -> str:
        return canonical_digest(self)


__all__ = [
    "EmbeddingInput",
    "EmbeddingOutput",
    "EmbeddingVector",
    "ModelCapabilityInput",
    "ModelCapabilityInvocation",
    "ModelCapabilityOutput",
    "ModelCapabilityResponse",
    "NamedScalar",
    "ProjectModelCapabilityClientPort",
    "ProjectModelCapabilityProviderPort",
    "ScoredCandidate",
    "ScoringCandidate",
    "ScoringInput",
    "ScoringOutput",
    "ValueInferenceInput",
    "ValueInferenceOutput",
]
