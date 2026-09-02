from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from noetrium_platform.capabilities.participant.core.api.contracts import ParticipantSessionRuntimeIdentity
from noetrium_platform.capabilities.participant.core.api.runtime import ParticipantSessionRuntime


ParticipantSessionRuntimeFactory = Callable[[], ParticipantSessionRuntime]


@dataclass(frozen=True, slots=True)
class RegisteredParticipantSessionRuntime:
    identity: ParticipantSessionRuntimeIdentity
    factory: ParticipantSessionRuntimeFactory


class ParticipantSessionRuntimeCatalog:
    """Session authority for runtime identities and session factories."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RegisteredParticipantSessionRuntime] = {}

    def register(
        self,
        identity: ParticipantSessionRuntimeIdentity,
        factory: ParticipantSessionRuntimeFactory,
    ) -> None:
        key = identity.digest()
        if key in self._runtimes:
            raise ValueError(
                "duplicate participant session runtime: "
                f"{identity.runtime_id}:{identity.runtime_version}"
            )
        self._runtimes[key] = RegisteredParticipantSessionRuntime(identity, factory)

    def resolve(self, identity: ParticipantSessionRuntimeIdentity) -> RegisteredParticipantSessionRuntime:
        try:
            registered = self._runtimes[identity.digest()]
        except KeyError as exc:
            raise KeyError(
                "unknown participant session runtime: "
                f"{identity.runtime_id}:{identity.runtime_version}"
            ) from exc
        if registered.identity != identity:
            raise ValueError("participant session runtime catalog identity collision")
        return registered

    def identities(self) -> tuple[ParticipantSessionRuntimeIdentity, ...]:
        return tuple(
            sorted(
                (row.identity for row in self._runtimes.values()),
                key=lambda row: row.digest(),
            )
        )


__all__ = [
    "ParticipantSessionRuntimeCatalog",
    "ParticipantSessionRuntimeFactory",
    "RegisteredParticipantSessionRuntime",
]
