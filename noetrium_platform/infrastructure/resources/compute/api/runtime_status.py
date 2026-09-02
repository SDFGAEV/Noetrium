from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class GpuDeviceStatus:
    index: str
    uuid: str
    name: str
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_percent: int

@dataclass(frozen=True, slots=True)
class GpuProcessStatus:
    pid: int
    gpu_uuid: str
    used_memory_mb: int
    process_name: str

@dataclass(frozen=True, slots=True)
class GpuRuntimeSnapshot:
    available: bool
    devices: tuple[GpuDeviceStatus, ...] = ()
    processes: tuple[GpuProcessStatus, ...] = ()
    detail: str = ""

class GpuRuntimeObserverPort(Protocol):
    def snapshot(self) -> GpuRuntimeSnapshot: ...

__all__ = ["GpuDeviceStatus", "GpuProcessStatus", "GpuRuntimeObserverPort", "GpuRuntimeSnapshot"]
