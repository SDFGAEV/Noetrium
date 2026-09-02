from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from noetrium_platform.foundation.kernel.kernel import ExecutionContext


class LifecyclePhase(StrEnum):
    NEW="new"; STARTING="starting"; READY="ready"; STOPPING="stopping"; STOPPED="stopped"; FAILED="failed"


@dataclass(frozen=True, slots=True)
class LifecycleSpec:
    component_id: str
    depends_on: tuple[str,...] = ()
    start_timeout_s: float = 120.0
    stop_timeout_s: float = 60.0
    heartbeat_interval_s: float | None = None

    def __post_init__(self) -> None:
        if not self.component_id: raise ValueError("component_id required")
        if self.component_id in self.depends_on: raise ValueError("component cannot depend on itself")
        if self.start_timeout_s <= 0 or self.stop_timeout_s <= 0: raise ValueError("lifecycle timeouts must be positive")
        if self.heartbeat_interval_s is not None and self.heartbeat_interval_s <= 0: raise ValueError("heartbeat interval must be positive")


@dataclass(frozen=True, slots=True)
class LifecycleEvidence:
    component_id: str
    phase: LifecyclePhase
    refs: tuple[str,...] = ()


class LifecycleComponent(Protocol):
    @property
    def lifecycle_spec(self) -> LifecycleSpec: ...
    def start(self, context: ExecutionContext) -> tuple[str,...]: ...
    def stop(self, context: ExecutionContext) -> tuple[str,...]: ...
