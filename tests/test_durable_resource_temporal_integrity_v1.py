from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from research_platform.reliability.recovery.api.lease import RecoveryLease
from research_platform.reliability.recovery.execution.runtime.file_lock import (
    FileLockedRecoveryExecutionFactory,
)
from research_platform.reliability.recovery.providers.lease_codec import (
    RECOVERY_LEASE_DOCUMENT_SCHEMA,
    RecoveryLeaseCodec,
    RecoveryLeaseIntegrityError,
)
from research_platform.reliability.recovery.providers.lease_store import RecoveryLeaseStore
from research_platform.resource.allocation.api import (
    EndpointAllocation,
    EndpointAllocationRequest,
    EndpointBindingProof,
    EndpointLeasePolicy,
    NetworkEndpoint,
)
from research_platform.resource.allocation.runtime import AtomicEndpointAllocator
from research_platform.resource.lease.api import (
    ResourceIdentity,
    ResourceKind,
    ResourceLease,
    ResourceOwner,
)
from research_platform.resource.lease.runtime import InMemoryResourceLeaseRegistry
from research_platform.resource.providers import (
    SQLiteEndpointAllocationStore,
    SQLiteResourceLeaseRegistry,
)
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


class _AvailableProbe:
    def probe(self, endpoint: NetworkEndpoint):
        from research_platform.resource.allocation.api import EndpointProbeResult
        return EndpointProbeResult(endpoint, True, "available")


class _LeaseStateStub:
    def acquire(self, *args, **kwargs): raise AssertionError("must not acquire")
    def renew(self, *args, **kwargs): raise AssertionError("must not renew")
    def assert_owned(self, *args, **kwargs): raise AssertionError("must not inspect")
    def release(self, *args, **kwargs): raise AssertionError("must not release")


def _resource_lease(*, expires_at: float | None = None) -> ResourceLease:
    return ResourceLease(
        "lease-a",
        ResourceIdentity(ResourceKind.COMPUTE, "host-a"),
        ScopeIdentity(ScopeKind.WORKSPACE, "workspace-a"),
        "temporal integrity",
        expires_at_epoch_s=expires_at,
    )


def test_resource_lease_rejects_non_finite_expiry_and_observation_time() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite positive"):
            _resource_lease(expires_at=value)
    lease = _resource_lease(expires_at=100.0)
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="observation time must be finite"):
            lease.expired_at(value)


def test_resource_lease_authorities_reject_non_finite_ttl_and_clock() -> None:
    resource = ResourceIdentity(ResourceKind.COMPUTE, "host-a")
    memory = InMemoryResourceLeaseRegistry()
    memory.register_owner(ResourceOwner(resource, PLATFORM_SCOPE))
    lease = ResourceLease("lease-a", resource, PLATFORM_SCOPE, "finite lease")
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite and > 0"):
            memory.acquire(lease, ttl_seconds=value, now=1.0)
        with pytest.raises(ValueError, match="observation time must be finite"):
            memory.acquire(lease, ttl_seconds=10.0, now=value)

    with TemporaryDirectory() as directory:
        database = Path(directory) / "resource.sqlite"
        sqlite = SQLiteResourceLeaseRegistry(database)
        sqlite.register_owner(ResourceOwner(resource, PLATFORM_SCOPE))
        for value in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="finite and > 0"):
                sqlite.acquire(lease, ttl_seconds=value, now=1.0)
            with pytest.raises(ValueError, match="observation time must be finite"):
                sqlite.acquire(lease, ttl_seconds=10.0, now=value)


def test_endpoint_temporal_contracts_reject_non_finite_values() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="ttl_seconds must be finite"):
            EndpointLeasePolicy(ttl_seconds=value, renewal_interval_seconds=1.0)
        with pytest.raises(ValueError, match="renewal_interval_seconds must be finite"):
            EndpointLeasePolicy(ttl_seconds=10.0, renewal_interval_seconds=value)
        with pytest.raises(ValueError, match="observation timestamp must be finite"):
            EndpointBindingProof(
                "allocation-a", NetworkEndpoint("127.0.0.1", 25565), 1,
                "a" * 64, value, "listener-evidence",
            )
        with pytest.raises(ValueError, match="lease expiry must be finite"):
            EndpointAllocation(
                "allocation-a", NetworkEndpoint("127.0.0.1", 25565), "lease-a",
                PLATFORM_SCOPE, "finite endpoint", "d" * 64,
                lease_expires_at_epoch_s=value,
            )


def test_endpoint_authorities_reject_non_finite_runtime_budgets() -> None:
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="lease_ttl_seconds must be finite"):
            AtomicEndpointAllocator(
                reservations=object(),  # type: ignore[arg-type]
                probe=_AvailableProbe(),
                lease_ttl_seconds=value,
            )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "endpoint.sqlite"
        store = SQLiteEndpointAllocationStore(path)
        request = EndpointAllocationRequest(
            "allocation-a", PLATFORM_SCOPE, "finite endpoint", "127.0.0.1", (25565,)
        )
        allocator = AtomicEndpointAllocator(reservations=store, probe=_AvailableProbe())
        reserved = allocator.allocate(request)
        for value in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="finite and > 0"):
                store.renew(reserved.allocation_id, ttl_seconds=value, now=1.0)
            with pytest.raises(ValueError, match="observation time must be finite"):
                store.reconcile_orphans(now=value)


def test_recovery_lease_rejects_non_finite_or_non_monotonic_timeline() -> None:
    with pytest.raises(ValueError, match="timestamps must be finite"):
        RecoveryLease("owner", "manifest", float("nan"), 2.0)
    with pytest.raises(ValueError, match="timestamps must be finite"):
        RecoveryLease("owner", "manifest", 1.0, float("inf"))
    with pytest.raises(ValueError, match="later than acquisition"):
        RecoveryLease("owner", "manifest", 2.0, 2.0)
    with pytest.raises(ValueError, match="owner and manifest identity"):
        RecoveryLease("", "manifest", 1.0, 2.0)


def test_recovery_store_and_execution_fence_reject_non_finite_ttl_and_clock() -> None:
    with TemporaryDirectory() as directory:
        store = RecoveryLeaseStore(Path(directory) / "recovery-lease.json")
        for value in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="ttl_seconds must be finite"):
                store.acquire("owner", "manifest", ttl_seconds=value, now=1.0)
            with pytest.raises(ValueError, match="observation time must be finite"):
                store.acquire("owner", "manifest", ttl_seconds=10.0, now=value)
            with pytest.raises(ValueError, match="ttl_seconds must be finite"):
                FileLockedRecoveryExecutionFactory(
                    _LeaseStateStub(), lock_path=Path(directory) / "recovery.lock"
                ).execution("owner", "manifest", ttl_seconds=value)


def test_recovery_codec_classifies_non_finite_json_as_integrity_failure() -> None:
    # JSON permits NaN in Python's permissive decoder, but it is not a canonical
    # platform value. The recovery boundary must turn that into typed integrity
    # failure rather than leak CanonicalEncodingError from the kernel.
    raw = json.dumps(
        {
            "schema": RECOVERY_LEASE_DOCUMENT_SCHEMA,
            "payload": {
                "owner_id": "owner",
                "manifest_digest": "manifest",
                "acquired_at": 1.0,
                "expires_at": float("nan"),
            },
            "payload_sha256": "0" * 64,
        },
        allow_nan=True,
    ).encode("utf-8")
    with pytest.raises(RecoveryLeaseIntegrityError, match="non-canonical"):
        RecoveryLeaseCodec().decode(raw)
