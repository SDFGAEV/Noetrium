from __future__ import annotations

from typing import Protocol

from research_platform.scope.api import ScopeIdentity

from .contracts import ComputeAllocation, ComputeCluster, ComputeHost, ComputeRequirement


class ComputeInventoryPort(Protocol):
    def register_host(self, host: ComputeHost) -> None: ...
    def host(self, host_id: str) -> ComputeHost: ...
    def list_hosts(self, *, scope: ScopeIdentity | None = None) -> tuple[ComputeHost, ...]: ...
    def register_cluster(self, cluster: ComputeCluster) -> None: ...
    def cluster(self, cluster_id: str) -> ComputeCluster: ...


class ComputeCandidatePort(Protocol):
    """Read-only capacity projection for preflight and planning consumers."""

    def candidates(
        self,
        requirement: ComputeRequirement,
        *,
        scope: ScopeIdentity | None = None,
    ) -> tuple[ComputeHost, ...]: ...


class ComputeSchedulerPort(ComputeCandidatePort, Protocol):
    def allocate(
        self,
        allocation_id: str,
        scope: ScopeIdentity,
        requirement: ComputeRequirement,
    ) -> ComputeAllocation: ...
    def release(self, allocation_id: str) -> None: ...
    def allocations(
        self,
        *,
        scope: ScopeIdentity | None = None,
    ) -> tuple[ComputeAllocation, ...]: ...


__all__ = [
    "ComputeCandidatePort",
    "ComputeInventoryPort",
    "ComputeSchedulerPort",
]
