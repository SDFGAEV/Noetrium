from __future__ import annotations

import heapq
import math
from dataclasses import replace
from threading import RLock
from time import time

from noetrium_platform.infrastructure.resources.lease.api import (
    LeaseState,
    ResourceIdentity,
    ResourceLease,
    ResourceLeaseConflict,
    ResourceLeaseExpired,
    ResourceOwner,
    ResourceOwnershipConflict,
)


class InMemoryResourceLeaseRegistry:
    """Indexed reference lease authority with optional TTL and fencing.

    Point operations touch only the requested lease/resource. Expiration uses a
    min-heap for explicit global reconciliation, so a large history of released
    leases does not turn acquire/get into a full-registry scan.
    """

    def __init__(self) -> None:
        self._owners: dict[ResourceIdentity, ResourceOwner] = {}
        self._leases: dict[str, ResourceLease] = {}
        self._active_by_resource: dict[ResourceIdentity, str] = {}
        self._last_fencing_by_resource: dict[ResourceIdentity, int] = {}
        self._expiry_heap: list[tuple[float, int, str]] = []
        self._lock = RLock()

    def register_owner(self, owner: ResourceOwner) -> None:
        with self._lock:
            existing = self._owners.get(owner.resource)
            if existing is not None and existing != owner:
                raise ResourceOwnershipConflict(owner.resource.key)
            self._owners[owner.resource] = owner

    def owner(self, resource: ResourceIdentity) -> ResourceOwner:
        with self._lock:
            try:
                return self._owners[resource]
            except KeyError as exc:
                raise KeyError(resource.key) from exc

    def remove_owner(self, resource: ResourceIdentity) -> None:
        with self._lock:
            self._expire_resource(resource, time())
            if resource in self._active_by_resource:
                raise ResourceOwnershipConflict(f"resource has active leases: {resource.key}")
            self._owners.pop(resource, None)

    @staticmethod
    def _same_lease_intent(existing: ResourceLease, requested: ResourceLease) -> bool:
        return (
            existing.lease_id == requested.lease_id
            and existing.resource == requested.resource
            and existing.holder_scope == requested.holder_scope
            and existing.purpose == requested.purpose
            and existing.holder_generation == requested.holder_generation
        )

    def _expire_lease_if_needed(self, lease_id: str, now_epoch_s: float) -> ResourceLease | None:
        current = self._leases.get(lease_id)
        if current is None or not current.expired_at(now_epoch_s):
            return current
        expired = replace(current, state=LeaseState.EXPIRED)
        self._leases[lease_id] = expired
        if self._active_by_resource.get(current.resource) == lease_id:
            self._active_by_resource.pop(current.resource, None)
        return expired

    def _expire_resource(self, resource: ResourceIdentity, now_epoch_s: float) -> None:
        lease_id = self._active_by_resource.get(resource)
        if lease_id is not None:
            self._expire_lease_if_needed(lease_id, now_epoch_s)

    def acquire(
        self,
        lease: ResourceLease,
        *,
        ttl_seconds: float | None = None,
        now: float | None = None,
    ) -> ResourceLease:
        now_epoch_s = time() if now is None else float(now)
        if not math.isfinite(now_epoch_s):
            raise ValueError("lease observation time must be finite")
        if ttl_seconds is not None and (
            not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0
        ):
            raise ValueError("lease ttl_seconds must be finite and > 0")
        with self._lock:
            if lease.resource not in self._owners:
                raise KeyError(lease.resource.key)
            self._expire_resource(lease.resource, now_epoch_s)
            existing = self._leases.get(lease.lease_id)
            if existing is not None:
                existing = self._expire_lease_if_needed(lease.lease_id, now_epoch_s)
                assert existing is not None
                if self._same_lease_intent(existing, lease) and existing.state is LeaseState.ACTIVE:
                    return existing
                raise ResourceLeaseConflict(lease.lease_id)
            active_id = self._active_by_resource.get(lease.resource)
            if active_id is not None:
                raise ResourceLeaseConflict(f"resource already has an active lease: {lease.resource.key}")
            fencing = self._last_fencing_by_resource.get(lease.resource, 0) + 1
            expires_at = lease.expires_at_epoch_s
            if ttl_seconds is not None:
                expires_at = now_epoch_s + ttl_seconds
            granted = replace(
                lease,
                state=LeaseState.ACTIVE,
                fencing_token=fencing,
                expires_at_epoch_s=expires_at,
            )
            self._leases[lease.lease_id] = granted
            self._active_by_resource[lease.resource] = lease.lease_id
            self._last_fencing_by_resource[lease.resource] = fencing
            if expires_at is not None:
                heapq.heappush(self._expiry_heap, (expires_at, fencing, lease.lease_id))
            return granted

    def renew(
        self,
        lease_id: str,
        *,
        fencing_token: int,
        ttl_seconds: float,
        now: float | None = None,
    ) -> ResourceLease:
        if not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0:
            raise ValueError("lease ttl_seconds must be finite and > 0")
        now_epoch_s = time() if now is None else float(now)
        if not math.isfinite(now_epoch_s):
            raise ValueError("lease observation time must be finite")
        with self._lock:
            current = self._expire_lease_if_needed(lease_id, now_epoch_s)
            if current is None:
                raise KeyError(lease_id)
            if current.state is LeaseState.EXPIRED:
                raise ResourceLeaseExpired(lease_id)
            if current.state is not LeaseState.ACTIVE or current.fencing_token != fencing_token:
                raise ResourceLeaseConflict(f"stale lease fencing token: {lease_id}")
            renewed = replace(current, expires_at_epoch_s=now_epoch_s + ttl_seconds)
            self._leases[lease_id] = renewed
            heapq.heappush(self._expiry_heap, (renewed.expires_at_epoch_s, renewed.fencing_token, lease_id))
            return renewed

    def release(self, lease_id: str) -> ResourceLease:
        with self._lock:
            current = self._expire_lease_if_needed(lease_id, time())
            if current is None:
                raise KeyError(lease_id)
            if current.state is not LeaseState.ACTIVE:
                return current
            released = replace(current, state=LeaseState.RELEASED)
            self._leases[lease_id] = released
            if self._active_by_resource.get(current.resource) == lease_id:
                self._active_by_resource.pop(current.resource, None)
            return released

    def get(self, lease_id: str) -> ResourceLease:
        with self._lock:
            current = self._expire_lease_if_needed(lease_id, time())
            if current is None:
                raise KeyError(lease_id)
            return current

    def active_for(self, resource: ResourceIdentity) -> tuple[ResourceLease, ...]:
        with self._lock:
            self._expire_resource(resource, time())
            lease_id = self._active_by_resource.get(resource)
            if lease_id is None:
                return ()
            return (self._leases[lease_id],)

    def reconcile_expired(self, *, now: float | None = None) -> tuple[ResourceLease, ...]:
        now_epoch_s = time() if now is None else float(now)
        if not math.isfinite(now_epoch_s):
            raise ValueError("lease observation time must be finite")
        expired: list[ResourceLease] = []
        with self._lock:
            while self._expiry_heap and self._expiry_heap[0][0] <= now_epoch_s:
                expires_at, fencing, lease_id = heapq.heappop(self._expiry_heap)
                current = self._leases.get(lease_id)
                if (
                    current is None
                    or current.state is not LeaseState.ACTIVE
                    or current.fencing_token != fencing
                    or current.expires_at_epoch_s != expires_at
                ):
                    continue
                value = self._expire_lease_if_needed(lease_id, now_epoch_s)
                if value is not None and value.state is LeaseState.EXPIRED:
                    expired.append(value)
        return tuple(expired)


__all__ = [
    "InMemoryResourceLeaseRegistry",
    "ResourceLeaseConflict",
    "ResourceLeaseExpired",
    "ResourceOwnershipConflict",
]
