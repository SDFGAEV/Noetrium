from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from research_platform.reliability.effect.api import EffectReconciliationDisposition, PreparedEffectHandle
from research_platform.platform.kernel import EffectClass, EffectReceipt, ExecutionContext, JsonObject, JsonValue, canonical_digest

from research_platform.participant._immutable_json import freeze_json_value, freeze_json_value_object


@dataclass(frozen=True, slots=True)
class CapabilityProviderIdentity:
    provider_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    interface_version: str
    request_schema: str
    result_schema: str
    effect_class: EffectClass = EffectClass.PURE
    deterministic: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.capability_id,
            self.interface_version,
            self.request_schema,
            self.result_schema,
        ):
            if not value.strip():
                raise ValueError("capability descriptor identity fields must be non-empty")


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    capability_id: str
    payload: JsonValue
    context: ExecutionContext
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability request identity is required")
        if not isinstance(self.context, ExecutionContext):
            raise TypeError("capability request context must be an ExecutionContext")
        if self.idempotency_key is not None and (
            not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip()
        ):
            raise ValueError("capability request idempotency_key must be non-empty when provided")
        object.__setattr__(
            self, "payload", freeze_json_value(self.payload, field="capability request payload")
        )


def capability_effect_request_id(request: CapabilityRequest) -> str:
    if not isinstance(request.idempotency_key, str) or not request.idempotency_key.strip():
        raise ValueError("effectful capability request requires a stable idempotency_key")
    slot = canonical_digest({
        "capability_id": request.capability_id,
        "idempotency_key": request.idempotency_key,
    })
    return f"capability-effect:{request.capability_id}:{slot[:24]}"


def capability_request_digest(request: CapabilityRequest) -> str:
    """Stable semantic identity for one capability request; excludes trace/span only data."""
    context = request.context
    return canonical_digest({
        "capability_id": request.capability_id,
        "payload": request.payload,
        "idempotency_key": request.idempotency_key,
        "run_id": context.run_id,
        "study_id": context.study_id,
        "lifetime_id": context.lifetime_id,
        "task_id": context.task_id,
        "decision_cycle_id": context.decision_cycle_id,
        "checkpoint_id": context.checkpoint_id,
        "participant_generations": context.participant_generations,
    })


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    capability_id: str
    payload: JsonValue
    generation: str | None = None
    artifacts: tuple[str, ...] = ()
    diagnostics: JsonObject = field(default_factory=dict)
    effect: EffectReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability result identity is required")
        if self.generation is not None and (
            not isinstance(self.generation, str) or not self.generation.strip()
        ):
            raise ValueError("capability result generation must be non-empty when provided")
        if not isinstance(self.artifacts, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.artifacts
        ):
            raise TypeError("capability result artifacts must be a tuple of non-empty strings")
        object.__setattr__(
            self, "payload", freeze_json_value(self.payload, field="capability result payload")
        )
        object.__setattr__(
            self, "diagnostics", freeze_json_value_object(self.diagnostics, field="capability result diagnostics")
        )


@dataclass(frozen=True, slots=True)
class CapabilityEffectReconciliationResult:
    capability_id: str
    disposition: EffectReconciliationDisposition
    result: CapabilityResult | None
    diagnostics: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability reconciliation identity is required")
        if self.result is not None and not isinstance(self.result, CapabilityResult):
            raise TypeError("capability reconciliation result must be CapabilityResult")
        object.__setattr__(
            self, "diagnostics",
            freeze_json_value_object(self.diagnostics, field="capability reconciliation diagnostics"),
        )


@runtime_checkable
class DurablePreparedCapabilitySession(Protocol):
    """Optional crash-durable effect capability implemented by a provider session.

    The provider owns opaque recovery semantics.  Platform code owns only the WAL
    envelope and exact request/receipt correlation.
    """

    effect_recovery_durability: str

    def prepare_capability_effect(
        self, request: CapabilityRequest
    ) -> PreparedEffectHandle: ...

    def execute_prepared_capability(
        self, request: CapabilityRequest, handle: PreparedEffectHandle
    ) -> CapabilityResult: ...

    def reconcile_prepared_capability(
        self, handle: PreparedEffectHandle, context: ExecutionContext
    ) -> CapabilityEffectReconciliationResult: ...


@runtime_checkable
class CapabilityPort(Protocol):
    """The only external-world surface visible to a generic Agent.

    Implementations may route to environments, tools, APIs, simulators, remote
    services, or other capability providers.  The consumer never receives the
    provider object itself.
    """

    def describe(self, capability_id: str) -> CapabilityDescriptor: ...
    def invoke(self, request: CapabilityRequest) -> CapabilityResult: ...


@runtime_checkable
class CapabilityExportSession(Protocol):
    """Optional capability surface that any runtime participant session may export."""

    @property
    def capabilities(self) -> tuple[CapabilityDescriptor, ...]: ...
    def invoke(self, request: CapabilityRequest) -> CapabilityResult: ...


@runtime_checkable
class CapabilityProviderSession(CapabilityExportSession, Protocol):
    def checkpoint(self) -> bytes: ...
    def restore(self, payload: bytes) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class CapabilityProviderImplementation(Protocol):
    """Capability implementation identity/behavior without session lifecycle authority."""
    @property
    def identity(self) -> CapabilityProviderIdentity: ...
