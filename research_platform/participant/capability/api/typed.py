from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, runtime_checkable

from research_platform.platform.kernel import EffectClass, ExecutionContext, canonical_digest

from .contracts import CapabilityDescriptor, CapabilityProviderIdentity


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _sha256(value: object, field: str) -> str:
    digest = _text(value, field)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


@runtime_checkable
class CapabilityInputCarrier(Protocol):
    @property
    def schema_id(self) -> str: ...

    def digest(self) -> str: ...


@runtime_checkable
class CapabilityOutputCarrier(Protocol):
    @property
    def schema_id(self) -> str: ...

    def digest(self) -> str: ...


InputCarrierT = TypeVar("InputCarrierT", bound=CapabilityInputCarrier)
OutputCarrierT = TypeVar("OutputCarrierT", bound=CapabilityOutputCarrier)


@dataclass(frozen=True, slots=True)
class TypedCapabilityRequest(Generic[InputCarrierT]):
    descriptor: CapabilityDescriptor
    payload: InputCarrierT
    context: ExecutionContext
    idempotency_key: str | None = None
    payload_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, CapabilityDescriptor):
            raise TypeError("typed capability request descriptor must be typed")
        if not isinstance(self.payload, CapabilityInputCarrier):
            raise TypeError("typed capability request payload must implement CapabilityInputCarrier")
        if self.payload.schema_id != self.descriptor.request_schema:
            raise ValueError("typed capability request schema does not match descriptor")
        payload_digest = _sha256(self.payload.digest(), "typed capability request payload digest")
        object.__setattr__(self, "payload_digest", payload_digest)
        if not isinstance(self.context, ExecutionContext):
            raise TypeError("typed capability request context must be ExecutionContext")
        if self.idempotency_key is not None:
            _text(self.idempotency_key, "typed capability request idempotency_key")

    def verify_payload_integrity(self) -> None:
        if self.payload.schema_id != self.descriptor.request_schema:
            raise ValueError("typed capability request schema drifted after construction")
        if self.payload.digest() != self.payload_digest:
            raise ValueError("typed capability request payload drifted after construction")

    def digest(self) -> str:
        context = self.context
        return canonical_digest({
            "descriptor": self.descriptor,
            "payload_digest": self.payload_digest,
            "idempotency_key": self.idempotency_key,
            "run_id": context.run_id,
            "study_id": context.study_id,
            "lifetime_id": context.lifetime_id,
            "task_id": context.task_id,
            "decision_cycle_id": context.decision_cycle_id,
            "checkpoint_id": context.checkpoint_id,
            "participant_generations": context.participant_generations,
        })


@dataclass(frozen=True, slots=True)
class TypedCapabilityResult(Generic[OutputCarrierT]):
    descriptor: CapabilityDescriptor
    payload: OutputCarrierT
    provider_identity: CapabilityProviderIdentity
    request_digest: str
    generation: str | None = None
    payload_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, CapabilityDescriptor):
            raise TypeError("typed capability result descriptor must be typed")
        if not isinstance(self.payload, CapabilityOutputCarrier):
            raise TypeError("typed capability result payload must implement CapabilityOutputCarrier")
        if self.payload.schema_id != self.descriptor.result_schema:
            raise ValueError("typed capability result schema does not match descriptor")
        payload_digest = _sha256(self.payload.digest(), "typed capability result payload digest")
        object.__setattr__(self, "payload_digest", payload_digest)
        if not isinstance(self.provider_identity, CapabilityProviderIdentity):
            raise TypeError("typed capability result provider identity must be typed")
        _sha256(self.request_digest, "typed capability result request digest")
        if self.generation is not None:
            _text(self.generation, "typed capability result generation")

    def verify_payload_integrity(self) -> None:
        if self.payload.schema_id != self.descriptor.result_schema:
            raise ValueError("typed capability result schema drifted after construction")
        if self.payload.digest() != self.payload_digest:
            raise ValueError("typed capability result payload drifted after construction")

    def digest(self) -> str:
        return canonical_digest({
            "descriptor": self.descriptor,
            "payload_digest": self.payload_digest,
            "provider_identity": self.provider_identity,
            "request_digest": self.request_digest,
            "generation": self.generation,
        })


@runtime_checkable
class TypedCapabilityPort(Protocol[InputCarrierT, OutputCarrierT]):
    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    def invoke_typed(
        self, request: TypedCapabilityRequest[InputCarrierT]
    ) -> TypedCapabilityResult[OutputCarrierT]: ...


def require_pure_typed_descriptor(descriptor: CapabilityDescriptor) -> None:
    if descriptor.effect_class is not EffectClass.PURE:
        raise ValueError("typed direct capability path is limited to pure capabilities")


__all__ = [
    "CapabilityInputCarrier",
    "CapabilityOutputCarrier",
    "TypedCapabilityPort",
    "TypedCapabilityRequest",
    "TypedCapabilityResult",
    "require_pure_typed_descriptor",
]
