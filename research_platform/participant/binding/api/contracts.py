from __future__ import annotations

from typing import Callable, Protocol

from research_platform.participant.core.api.contracts import (
    ParticipantConfigurationArtifact,
    ParticipantImplementationIdentity,
    ParticipantRuntimeBinding,
    ParticipantSessionRuntimeIdentity,
)
from research_platform.participant.core.api.runtime import (
    ParticipantRuntimeEndpoint,
    ParticipantRuntimeHandle,
    ParticipantSessionRuntime,
)


class ParticipantImplementationRegistration(Protocol):
    identity: ParticipantImplementationIdentity
    factory: Callable[[ParticipantConfigurationArtifact], object]


class ParticipantImplementationCatalogPort(Protocol):
    def resolve(
        self,
        identity: ParticipantImplementationIdentity,
    ) -> ParticipantImplementationRegistration: ...


class ParticipantConfigurationCatalogPort(Protocol):
    def resolve(self, configuration_digest: str) -> ParticipantConfigurationArtifact: ...


class ParticipantSessionRuntimeRegistration(Protocol):
    identity: ParticipantSessionRuntimeIdentity
    factory: Callable[[], ParticipantSessionRuntime]


class ParticipantSessionRuntimeCatalogPort(Protocol):
    def resolve(
        self,
        identity: ParticipantSessionRuntimeIdentity,
    ) -> ParticipantSessionRuntimeRegistration: ...


ParticipantRuntimeEndpointFactory = Callable[
    [ParticipantImplementationIdentity, ParticipantSessionRuntimeIdentity, object, ParticipantSessionRuntime],
    ParticipantRuntimeEndpoint,
]


class ParticipantBindingResolverPort(Protocol):
    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle: ...


__all__ = [
    "ParticipantBindingResolverPort",
    "ParticipantConfigurationCatalogPort",
    "ParticipantImplementationCatalogPort",
    "ParticipantImplementationRegistration",
    "ParticipantRuntimeEndpointFactory",
    "ParticipantSessionRuntimeCatalogPort",
    "ParticipantSessionRuntimeRegistration",
]
