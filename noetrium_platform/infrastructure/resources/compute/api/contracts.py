from __future__ import annotations

from dataclasses import dataclass

from noetrium_platform.foundation.scope.api import ScopeIdentity


@dataclass(frozen=True, slots=True)
class ComputeGPU:
    gpu_id: str
    memory_bytes: int
    model: str = ""
    labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.gpu_id.strip() or self.memory_bytes < 1:
            raise ValueError("GPU identity/memory must be valid")


@dataclass(frozen=True, slots=True)
class ComputeHost:
    host_id: str
    scope: ScopeIdentity
    cpu_cores: int
    memory_bytes: int
    gpus: tuple[ComputeGPU, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.host_id.strip() or self.cpu_cores < 1 or self.memory_bytes < 1:
            raise ValueError("host identity/capacity must be valid")
        if len({gpu.gpu_id for gpu in self.gpus}) != len(self.gpus):
            raise ValueError("GPU identities must be unique within a host")


@dataclass(frozen=True, slots=True)
class ComputeCluster:
    cluster_id: str
    scope: ScopeIdentity
    host_ids: tuple[str, ...]
    labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.cluster_id.strip():
            raise ValueError("cluster_id must be non-empty")


@dataclass(frozen=True, slots=True)
class ComputeRequirement:
    cpu_cores: int = 1
    memory_bytes: int = 1
    gpu_count: int = 0
    minimum_gpu_memory_bytes: int = 0
    required_labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.cpu_cores < 1 or self.memory_bytes < 1 or self.gpu_count < 0 or self.minimum_gpu_memory_bytes < 0:
            raise ValueError("compute requirements must be non-negative and include CPU/memory")


@dataclass(frozen=True, slots=True)
class ComputeAllocation:
    allocation_id: str
    scope: ScopeIdentity
    host_id: str
    cpu_cores: int
    memory_bytes: int
    gpu_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.allocation_id.strip() or not self.host_id.strip():
            raise ValueError("allocation identity/host must be non-empty")


__all__ = ["ComputeAllocation", "ComputeCluster", "ComputeGPU", "ComputeHost", "ComputeRequirement"]
