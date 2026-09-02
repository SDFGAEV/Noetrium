from __future__ import annotations

from threading import RLock

from noetrium_platform.infrastructure.resources.compute.api import ComputeCluster, ComputeHost
from noetrium_platform.foundation.scope.api import ScopeIdentity


class InMemoryComputeInventory:
    """Thread-safe observation/catalog projection for compute resources.

    This class is intentionally non-durable. It is suitable for a projection or
    test authority; durable fleet identity belongs in a persistent provider.
    """

    def __init__(self) -> None:
        self._hosts: dict[str, ComputeHost] = {}
        self._clusters: dict[str, ComputeCluster] = {}
        self._lock = RLock()

    def register_host(self, host: ComputeHost) -> None:
        with self._lock:
            current = self._hosts.get(host.host_id)
            if current is not None and current != host:
                raise ValueError(f"host identity already registered: {host.host_id}")
            self._hosts[host.host_id] = host

    def host(self, host_id: str) -> ComputeHost:
        with self._lock:
            try:
                return self._hosts[host_id]
            except KeyError as exc:
                raise KeyError(host_id) from exc

    def list_hosts(self, *, scope: ScopeIdentity | None = None) -> tuple[ComputeHost, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (host for host in self._hosts.values() if scope is None or host.scope == scope),
                    key=lambda host: host.host_id,
                )
            )

    def register_cluster(self, cluster: ComputeCluster) -> None:
        with self._lock:
            missing = [host_id for host_id in cluster.host_ids if host_id not in self._hosts]
            if missing:
                raise KeyError(missing[0])
            current = self._clusters.get(cluster.cluster_id)
            if current is not None and current != cluster:
                raise ValueError(f"cluster identity already registered: {cluster.cluster_id}")
            self._clusters[cluster.cluster_id] = cluster

    def cluster(self, cluster_id: str) -> ComputeCluster:
        with self._lock:
            try:
                return self._clusters[cluster_id]
            except KeyError as exc:
                raise KeyError(cluster_id) from exc


__all__ = ["InMemoryComputeInventory"]
