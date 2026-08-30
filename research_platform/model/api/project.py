from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from research_platform.model.request._immutable_json import freeze_json_object
from research_platform.model.request.api import ModelRequestEnvelope
from research_platform.model.serving.endpoint.api import ModelEndpointResponse
from research_platform.platform.kernel import (
    ImmutableModelIdentity,
    JsonInput,
    JsonValue,
    canonical_digest,
)


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value


def _sha256(value: object, field_name: str) -> str:
    digest = _text(value, field_name)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return digest


def _tokens(values: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    normalized = tuple(sorted(_text(value, field_name) for value in values))
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ModelCapabilityRequirement:
    """Project-owned model capability and exact model-visible request requirement."""

    role: str
    prompt_generation_id: str
    prompt_id: str
    prompt_digest: str
    required_capabilities: tuple[str, ...] = ()
    minimum_context_tokens: int = 1
    tool_schema_sha256: str | None = None

    def __post_init__(self) -> None:
        _text(self.role, "model requirement role")
        _text(self.prompt_generation_id, "model requirement prompt_generation_id")
        _text(self.prompt_id, "model requirement prompt_id")
        _sha256(self.prompt_digest, "model requirement prompt_digest")
        object.__setattr__(
            self,
            "required_capabilities",
            _tokens(self.required_capabilities, "model requirement capabilities"),
        )
        if type(self.minimum_context_tokens) is not int or self.minimum_context_tokens <= 0:
            raise ValueError("model requirement minimum_context_tokens must be positive")
        if self.tool_schema_sha256 is not None:
            _sha256(self.tool_schema_sha256, "model requirement tool_schema_sha256")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ModelProviderProfile:
    provider_id: str
    capabilities: tuple[str, ...]
    schema_version: str = "project-model-provider.v1"

    def __post_init__(self) -> None:
        _text(self.provider_id, "model provider_id")
        if self.schema_version != "project-model-provider.v1":
            raise ValueError("unsupported project model provider schema")
        object.__setattr__(
            self,
            "capabilities",
            _tokens(self.capabilities, "model provider capabilities"),
        )

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ProjectModelBinding:
    """Project-visible qualified model provenance with no route/process authority."""

    requirement_digest: str
    provider_id: str
    provider_profile_digest: str
    role: str
    model: ImmutableModelIdentity
    deployment_id: str
    deployment_generation: str
    model_stack_digest: str
    qualification_certificate_digest: str
    runtime_qualification_digest: str
    host_identity_digest: str
    prompt_generation_id: str
    prompt_id: str
    prompt_digest: str
    capabilities: tuple[str, ...]
    runtime_canary_evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "requirement_digest",
            "provider_profile_digest",
            "deployment_generation",
            "model_stack_digest",
            "qualification_certificate_digest",
            "runtime_qualification_digest",
            "host_identity_digest",
            "prompt_digest",
        ):
            _sha256(getattr(self, field_name), f"project model binding {field_name}")
        for field_name in (
            "provider_id",
            "role",
            "deployment_id",
            "prompt_generation_id",
            "prompt_id",
        ):
            _text(getattr(self, field_name), f"project model binding {field_name}")
        if not isinstance(self.model, ImmutableModelIdentity):
            raise TypeError("project model binding model must be ImmutableModelIdentity")
        object.__setattr__(
            self,
            "capabilities",
            _tokens(self.capabilities, "project model binding capabilities"),
        )
        if not isinstance(self.runtime_canary_evidence_digests, tuple):
            raise TypeError("project model binding canary evidence must be a tuple")
        for digest in self.runtime_canary_evidence_digests:
            _sha256(digest, "project model binding runtime canary evidence digest")
        if len(set(self.runtime_canary_evidence_digests)) != len(
            self.runtime_canary_evidence_digests
        ):
            raise ValueError("project model binding canary evidence must be unique")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ProjectModelRequest:
    requirement_digest: str
    envelope: ModelRequestEnvelope
    body: Mapping[str, JsonInput]
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha256(self.requirement_digest, "project model request requirement_digest")
        if not isinstance(self.envelope, ModelRequestEnvelope):
            raise TypeError("project model request envelope must be ModelRequestEnvelope")
        if not isinstance(self.body, Mapping):
            raise TypeError("project model request body must be a mapping")
        frozen_body = freeze_json_object(self.body, field="project model request body")
        object.__setattr__(self, "body", frozen_body)
        object.__setattr__(
            self,
            "request_digest",
            canonical_digest(
                {
                    "requirement_digest": self.requirement_digest,
                    "envelope_digest": self.envelope.envelope_digest,
                    "body": dict(frozen_body),
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ProjectModelResponse:
    request_digest: str
    binding_digest: str
    response: ModelEndpointResponse

    def __post_init__(self) -> None:
        _sha256(self.request_digest, "project model response request_digest")
        _sha256(self.binding_digest, "project model response binding_digest")
        if not isinstance(self.response, ModelEndpointResponse):
            raise TypeError("project model response must carry ModelEndpointResponse")


class ModelBindingDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ModelBindingDiagnosticCode(StrEnum):
    CAPABILITY_MISSING = "MODEL_CAPABILITY_MISSING"
    QUALIFIED_BINDING_UNAVAILABLE = "MODEL_QUALIFIED_BINDING_UNAVAILABLE"
    CONTEXT_INSUFFICIENT = "MODEL_CONTEXT_INSUFFICIENT"
    BINDING_PROVENANCE_DRIFT = "MODEL_BINDING_PROVENANCE_DRIFT"


@dataclass(frozen=True, slots=True)
class ModelBindingDiagnostic:
    code: ModelBindingDiagnosticCode
    severity: ModelBindingDiagnosticSeverity
    message: str
    requirement_digest: str
    provider_id: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, ModelBindingDiagnosticCode):
            raise TypeError("model diagnostic code must be typed")
        if not isinstance(self.severity, ModelBindingDiagnosticSeverity):
            raise TypeError("model diagnostic severity must be typed")
        _text(self.message, "model diagnostic message")
        _sha256(self.requirement_digest, "model diagnostic requirement_digest")
        _text(self.provider_id, "model diagnostic provider_id")
        if not isinstance(self.evidence_refs, tuple) or any(
            not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs
        ):
            raise TypeError("model diagnostic evidence_refs must be non-empty strings")


class ModelProjectBindingError(RuntimeError):
    def __init__(self, diagnostics: tuple[ModelBindingDiagnostic, ...]) -> None:
        if not diagnostics:
            raise ValueError("model binding error requires typed diagnostics")
        self.diagnostics = diagnostics
        super().__init__("; ".join(row.message for row in diagnostics))


@runtime_checkable
class ProjectModelClientPort(Protocol):
    @property
    def binding(self) -> ProjectModelBinding: ...

    def complete(self, request: ProjectModelRequest) -> ProjectModelResponse: ...


@runtime_checkable
class ProjectModelProviderPort(Protocol):
    @property
    def profile(self) -> ModelProviderProfile: ...

    def bind(self, requirement: ModelCapabilityRequirement) -> ProjectModelClientPort: ...

    def diagnose(
        self, requirement: ModelCapabilityRequirement
    ) -> tuple[ModelBindingDiagnostic, ...]: ...


__all__ = [
    "ModelBindingDiagnostic",
    "ModelBindingDiagnosticCode",
    "ModelBindingDiagnosticSeverity",
    "ModelCapabilityRequirement",
    "ModelProjectBindingError",
    "ModelProviderProfile",
    "ProjectModelBinding",
    "ProjectModelClientPort",
    "ProjectModelProviderPort",
    "ProjectModelRequest",
    "ProjectModelResponse",
]
