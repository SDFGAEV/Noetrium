from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from noetrium_platform.infrastructure.resources.compute.api import ComputeAllocation, ComputeRequirement
from noetrium_platform.foundation.scope.api import ScopeIdentity

from .inventory import InMemoryComputeInventory


@dataclass(slots=True)
class _HostUsage:
    cpu_cores: int = 0
    memory_bytes: int = 0
    gpu_ids: set[str] = field(default_factory=set)


class InMemoryComputeScheduler:
    """Linearizable in-process capacity scheduler with O(hosts + GPUs) selection.

    It is deliberately an in-memory authority. Cross-process durable allocation
    is provided separately; callers must not treat this class as restart-safe.
    """

    def __init__(self, inventory: InMemoryComputeInventory) -> None:
        self._inventory = inventory
        self._allocations: dict[str, ComputeAllocation] = {}
        self._usage_by_host: dict[str, _HostUsage] = {}
        self._lock = RLock()

    def _usage(self, host_id: str) -> _HostUsage:
        return self._usage_by_host.get(host_id, _HostUsage())

    def _candidates_locked(
        self,
        requirement: ComputeRequirement,
        *,
        scope: ScopeIdentity | None,
    ):
        result = []
        required_labels = dict(requirement.required_labels)
        for host in self._inventory.list_hosts(scope=scope):
            if not host.enabled:
                continue
            if any(dict(host.labels).get(key) != value for key, value in required_labels.items()):
                continue
            usage = self._usage(host.host_id)
            available_gpus = tuple(
                gpu.gpu_id
                for gpu in host.gpus
                if gpu.gpu_id not in usage.gpu_ids
                and gpu.memory_bytes >= requirement.minimum_gpu_memory_bytes
            )
            if host.cpu_cores - usage.cpu_cores < requirement.cpu_cores:
                continue
            if host.memory_bytes - usage.memory_bytes < requirement.memory_bytes:
                continue
            if len(available_gpus) < requirement.gpu_count:
                continue
            result.append(host)
        return tuple(result)

    def candidates(
        self,
        requirement: ComputeRequirement,
        *,
        scope: ScopeIdentity | None = None,
    ):
        with self._lock:
            return self._candidates_locked(requirement, scope=scope)

    def allocate(
        self,
        allocation_id: str,
        scope: ScopeIdentity,
        requirement: ComputeRequirement,
    ) -> ComputeAllocation:
        with self._lock:
            if allocation_id in self._allocations:
                raise ValueError(f"allocation already exists: {allocation_id}")
            hosts = self._candidates_locked(requirement, scope=scope)
            if not hosts:
                raise RuntimeError("no compute host satisfies requirement")
            host = hosts[0]
            usage = self._usage(host.host_id)
            gpu_ids = tuple(
                gpu.gpu_id
                for gpu in host.gpus
                if gpu.gpu_id not in usage.gpu_ids
                and gpu.memory_bytes >= requirement.minimum_gpu_memory_bytes
            )[: requirement.gpu_count]
            row = ComputeAllocation(
                allocation_id,
                scope,
                host.host_id,
                requirement.cpu_cores,
                requirement.memory_bytes,
                gpu_ids,
            )
            self._allocations[allocation_id] = row
            updated = _HostUsage(
                cpu_cores=usage.cpu_cores + row.cpu_cores,
                memory_bytes=usage.memory_bytes + row.memory_bytes,
                gpu_ids=set(usage.gpu_ids).union(row.gpu_ids),
            )
            self._usage_by_host[host.host_id] = updated
            return row

    def release(self, allocation_id: str) -> None:
        with self._lock:
            row = self._allocations.pop(allocation_id, None)
            if row is None:
                return
            usage = self._usage_by_host.get(row.host_id)
            if usage is None:
                raise RuntimeError(f"compute usage index missing for allocation: {allocation_id}")
            remaining_gpus = set(usage.gpu_ids)
            remaining_gpus.difference_update(row.gpu_ids)
            next_usage = _HostUsage(
                cpu_cores=usage.cpu_cores - row.cpu_cores,
                memory_bytes=usage.memory_bytes - row.memory_bytes,
                gpu_ids=remaining_gpus,
            )
            if next_usage.cpu_cores < 0 or next_usage.memory_bytes < 0:
                raise RuntimeError(f"compute usage index underflow: {allocation_id}")
            if next_usage.cpu_cores or next_usage.memory_bytes or next_usage.gpu_ids:
                self._usage_by_host[row.host_id] = next_usage
            else:
                self._usage_by_host.pop(row.host_id, None)

    def allocations(
        self,
        *,
        scope: ScopeIdentity | None = None,
    ) -> tuple[ComputeAllocation, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        allocation
                        for allocation in self._allocations.values()
                        if scope is None or allocation.scope == scope
                    ),
                    key=lambda allocation: allocation.allocation_id,
                )
            )


__all__ = ["InMemoryComputeScheduler"]
