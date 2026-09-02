from __future__ import annotations

from typing import Mapping, Protocol

from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonObject

from .contracts import RawObservationReceipt, RawObservationSchema


class RawObservationPersistencePort(Protocol):
    def append(
        self,
        context: ExecutionContext,
        schema: RawObservationSchema,
        payload: JsonObject,
        *,
        timestamp: float | None,
        idempotency_key: str | None,
    ) -> RawObservationReceipt: ...

    def verify(self, run_id: str, family: str) -> tuple[str, ...]: ...

    def close(self) -> None: ...


__all__ = ["RawObservationPersistencePort"]
