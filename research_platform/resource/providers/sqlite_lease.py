from __future__ import annotations

import math
import sqlite3

from dataclasses import replace
from pathlib import Path
from time import time

from research_platform.resource.lease.api import (
    LeaseState,
    ResourceIdentity,
    ResourceKind,
    ResourceLease,
    ResourceLeaseConflict,
    ResourceLeaseExpired,
    ResourceOwner,
    ResourceOwnership,
    ResourceLeasePort,
    ResourceOwnershipConflict,
    ResourceOwnershipPort,
)
from research_platform.resource.providers.sqlite_connection import durable_sqlite_connection
from research_platform.resource.providers.sqlite_resource import (
    RESOURCE_SCHEMA_VERSION,
    ensure_resource_schema,
    expire_lease,
    expire_resource,
    next_fencing_token,
)
from research_platform.scope.api import ScopeIdentity, ScopeKind


class SQLiteResourceLeaseRegistry(ResourceOwnershipPort, ResourceLeasePort):
    """Durable owner/lease authority with TTL, renewal and monotonic fencing.

    Point operations expire only the addressed lease/resource. Global expiry is
    reserved for explicit reconciliation, avoiding hidden O(total leases) work
    in acquire/get/release hot paths.
    """

    SCHEMA_VERSION = RESOURCE_SCHEMA_VERSION

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("SQLite resource timeout_seconds must be finite and positive")
        self.timeout_seconds = float(timeout_seconds)
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                ensure_resource_schema(conn)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def _connection(self):
        return durable_sqlite_connection(self.path, timeout_seconds=self.timeout_seconds)

    @staticmethod
    def _resource_values(resource: ResourceIdentity) -> tuple[str, str, str]:
        return resource.key, resource.kind.value, resource.resource_id

    @staticmethod
    def _scope_values(scope: ScopeIdentity) -> tuple[str, str]:
        return scope.kind.value, scope.scope_id

    @staticmethod
    def _decode_owner(row: tuple[object, ...]) -> ResourceOwner:
        return ResourceOwner(
            ResourceIdentity(ResourceKind(str(row[1])), str(row[2])),
            ScopeIdentity(ScopeKind(str(row[3])), str(row[4])),
            ResourceOwnership(str(row[5])),
        )

    @staticmethod
    def _decode_lease(row: tuple[object, ...]) -> ResourceLease:
        return ResourceLease(
            str(row[0]),
            ResourceIdentity(ResourceKind(str(row[2])), str(row[3])),
            ScopeIdentity(ScopeKind(str(row[4])), str(row[5])),
            str(row[6]),
            LeaseState(str(row[7])),
            int(row[8]),
            int(row[9]),
            None if row[10] is None else float(row[10]),
        )

    @staticmethod
    def _same_lease_intent(existing: ResourceLease, requested: ResourceLease) -> bool:
        return (
            existing.lease_id == requested.lease_id
            and existing.resource == requested.resource
            and existing.holder_scope == requested.holder_scope
            and existing.purpose == requested.purpose
            and existing.holder_generation == requested.holder_generation
        )

    def register_owner(self, owner: ResourceOwner) -> None:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM resource_owners WHERE resource_key=?", (owner.resource.key,)).fetchone()
            if row is not None:
                if self._decode_owner(row) != owner:
                    conn.rollback()
                    raise ResourceOwnershipConflict(owner.resource.key)
                conn.commit()
                return
            resource_key, kind, resource_id = self._resource_values(owner.resource)
            scope_kind, scope_id = self._scope_values(owner.scope)
            conn.execute(
                "INSERT INTO resource_owners(resource_key,resource_kind,resource_id,scope_kind,scope_id,ownership) VALUES(?,?,?,?,?,?)",
                (resource_key, kind, resource_id, scope_kind, scope_id, owner.ownership.value),
            )
            conn.commit()

    def owner(self, resource: ResourceIdentity) -> ResourceOwner:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM resource_owners WHERE resource_key=?", (resource.key,)).fetchone()
        if row is None:
            raise KeyError(resource.key)
        return self._decode_owner(row)

    def remove_owner(self, resource: ResourceIdentity) -> None:
        now_epoch_s = time()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expire_resource(conn, resource.key, now_epoch_s)
            active = conn.execute(
                "SELECT 1 FROM resource_leases WHERE resource_key=? AND state='active'", (resource.key,)
            ).fetchone()
            if active is not None:
                conn.rollback()
                raise ResourceOwnershipConflict(f"resource has active leases: {resource.key}")
            conn.execute("DELETE FROM resource_owners WHERE resource_key=?", (resource.key,))
            conn.commit()

    def acquire(
        self,
        lease: ResourceLease,
        *,
        ttl_seconds: float | None = None,
        now: float | None = None,
    ) -> ResourceLease:
        if ttl_seconds is not None and (
            not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0
        ):
            raise ValueError("lease ttl_seconds must be finite and > 0")
        now_epoch_s = time() if now is None else float(now)
        if not math.isfinite(now_epoch_s):
            raise ValueError("lease observation time must be finite")
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            owner = conn.execute("SELECT 1 FROM resource_owners WHERE resource_key=?", (lease.resource.key,)).fetchone()
            if owner is None:
                conn.rollback()
                raise KeyError(lease.resource.key)
            expire_resource(conn, lease.resource.key, now_epoch_s)
            row = conn.execute("SELECT * FROM resource_leases WHERE lease_id=?", (lease.lease_id,)).fetchone()
            if row is not None:
                existing = self._decode_lease(row)
                if self._same_lease_intent(existing, lease) and existing.state is LeaseState.ACTIVE:
                    conn.commit()
                    return existing
                conn.rollback()
                raise ResourceLeaseConflict(lease.lease_id)
            active = conn.execute(
                "SELECT 1 FROM resource_leases WHERE resource_key=? AND state='active'", (lease.resource.key,)
            ).fetchone()
            if active is not None:
                conn.rollback()
                raise ResourceLeaseConflict(f"resource already has an active lease: {lease.resource.key}")
            fencing = next_fencing_token(conn, lease.resource.key)
            expires_at = lease.expires_at_epoch_s if ttl_seconds is None else now_epoch_s + ttl_seconds
            granted = replace(
                lease,
                state=LeaseState.ACTIVE,
                fencing_token=fencing,
                expires_at_epoch_s=expires_at,
            )
            resource_key, kind, resource_id = self._resource_values(granted.resource)
            scope_kind, scope_id = self._scope_values(granted.holder_scope)
            try:
                conn.execute(
                    """
                    INSERT INTO resource_leases(
                        lease_id,resource_key,resource_kind,resource_id,
                        holder_scope_kind,holder_scope_id,purpose,state,
                        holder_generation,fencing_token,expires_at_epoch_s
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        granted.lease_id, resource_key, kind, resource_id,
                        scope_kind, scope_id, granted.purpose, granted.state.value,
                        granted.holder_generation, granted.fencing_token, granted.expires_at_epoch_s,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ResourceLeaseConflict(granted.lease_id) from exc
            conn.commit()
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
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expire_lease(conn, lease_id, now_epoch_s)
            row = conn.execute("SELECT * FROM resource_leases WHERE lease_id=?", (lease_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(lease_id)
            current = self._decode_lease(row)
            if current.state is LeaseState.EXPIRED:
                conn.rollback()
                raise ResourceLeaseExpired(lease_id)
            if current.state is not LeaseState.ACTIVE or current.fencing_token != fencing_token:
                conn.rollback()
                raise ResourceLeaseConflict(f"stale lease fencing token: {lease_id}")
            expires_at = now_epoch_s + ttl_seconds
            conn.execute(
                "UPDATE resource_leases SET expires_at_epoch_s=? WHERE lease_id=? AND state='active' AND fencing_token=?",
                (expires_at, lease_id, fencing_token),
            )
            conn.commit()
            return replace(current, expires_at_epoch_s=expires_at)

    def release(self, lease_id: str) -> ResourceLease:
        now_epoch_s = time()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expire_lease(conn, lease_id, now_epoch_s)
            row = conn.execute("SELECT * FROM resource_leases WHERE lease_id=?", (lease_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(lease_id)
            current = self._decode_lease(row)
            if current.state is LeaseState.ACTIVE:
                conn.execute("UPDATE resource_leases SET state='released' WHERE lease_id=?", (lease_id,))
                current = replace(current, state=LeaseState.RELEASED)
            conn.commit()
            return current

    def get(self, lease_id: str) -> ResourceLease:
        now_epoch_s = time()
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM resource_leases WHERE lease_id=?", (lease_id,)).fetchone()
        if row is None:
            raise KeyError(lease_id)
        current = self._decode_lease(row)
        if not current.expired_at(now_epoch_s):
            return current
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expire_lease(conn, lease_id, now_epoch_s)
            row = conn.execute("SELECT * FROM resource_leases WHERE lease_id=?", (lease_id,)).fetchone()
            conn.commit()
        if row is None:
            raise KeyError(lease_id)
        return self._decode_lease(row)

    def active_for(self, resource: ResourceIdentity) -> tuple[ResourceLease, ...]:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expire_resource(conn, resource.key, time())
            rows = conn.execute(
                "SELECT * FROM resource_leases WHERE resource_key=? AND state='active' ORDER BY lease_id",
                (resource.key,),
            ).fetchall()
            conn.commit()
        return tuple(self._decode_lease(row) for row in rows)

    def reconcile_expired(self, *, now: float | None = None) -> tuple[ResourceLease, ...]:
        now_epoch_s = time() if now is None else float(now)
        if not math.isfinite(now_epoch_s):
            raise ValueError("lease observation time must be finite")
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                UPDATE resource_leases SET state='expired'
                WHERE state='active' AND expires_at_epoch_s IS NOT NULL AND expires_at_epoch_s<=?
                RETURNING *
                """,
                (now_epoch_s,),
            ).fetchall()
            conn.commit()
        return tuple(self._decode_lease(row) for row in rows)


__all__ = ["SQLiteResourceLeaseRegistry"]
