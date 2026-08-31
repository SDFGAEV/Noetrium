from __future__ import annotations

from typing import Callable, Generic

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityProviderIdentity,
    TypedCapabilityRequest,
    TypedCapabilityResult,
    require_pure_typed_descriptor,
)
from research_platform.participant.capability.api.typed import InputCarrierT, OutputCarrierT


class FunctionalTypedCapabilityProvider(Generic[InputCarrierT, OutputCarrierT]):
    """Reference pure typed-capability implementation without routing authority."""

    def __init__(
        self,
        *,
        identity: CapabilityProviderIdentity,
        descriptor: CapabilityDescriptor,
        handler: Callable[[InputCarrierT, ExecutionContext], OutputCarrierT],
    ) -> None:
        if not isinstance(identity, CapabilityProviderIdentity):
            raise TypeError("typed capability provider identity must be typed")
        if not isinstance(descriptor, CapabilityDescriptor):
            raise TypeError("typed capability provider descriptor must be typed")
        require_pure_typed_descriptor(descriptor)
        self._identity = identity
        self._descriptor = descriptor
        self._handler = handler

    @property
    def identity(self) -> CapabilityProviderIdentity:
        return self._identity

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke_typed(
        self, request: TypedCapabilityRequest[InputCarrierT]
    ) -> TypedCapabilityResult[OutputCarrierT]:
        if request.descriptor != self._descriptor:
            raise ValueError("typed capability request descriptor does not match provider descriptor")
        request.verify_payload_integrity()
        payload = self._handler(request.payload, request.context)
        request.verify_payload_integrity()
        return TypedCapabilityResult(
            descriptor=self._descriptor,
            payload=payload,
            provider_identity=self._identity,
            request_digest=request.digest(),
        )


__all__ = ["FunctionalTypedCapabilityProvider"]
