from __future__ import annotations

import math
from pathlib import Path
import time

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes, durable_unlink
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock

from research_platform.reliability.recovery.api.lease import RecoveryLease, RecoveryLeaseBusy
from .lease_codec import RecoveryLeaseCodec


class RecoveryLeaseStore:
    """Durable owner/manifest/TTL state only; execution fencing is a separate authority."""

    def __init__(self, path: Path, codec: RecoveryLeaseCodec | None = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.codec = codec or RecoveryLeaseCodec()
        self._guard = InterprocessFileLock(path.with_name(path.name + ".guard.lock"))

    def read(self) -> RecoveryLease | None:
        if not self.path.exists():
            return None
        return self.codec.decode(self.path.read_bytes())

    def evidence_refs(self) -> tuple[str, ...]:
        return (str(self.path),)

    def acquire(
        self,
        owner_id: str,
        manifest_digest: str,
        *,
        ttl_seconds: float = 300.0,
        now: float | None = None,
    ) -> RecoveryLease:
        if not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be finite and positive")
        t = time.time() if now is None else float(now)
        if not math.isfinite(t):
            raise ValueError("recovery lease observation time must be finite")
        with self._guard:
            current = self.read()
            if current and current.expires_at > t:
                if current.owner_id != owner_id or current.manifest_digest != manifest_digest:
                    raise RecoveryLeaseBusy(
                        f"runtime recovery lease held by {current.owner_id} for a different owner/manifest"
                    )
            lease = RecoveryLease(owner_id, manifest_digest, t, t + ttl_seconds)
            atomic_replace_bytes(self.path, self.codec.encode(lease))
            return lease

    def renew(
        self,
        owner_id: str,
        manifest_digest: str,
        *,
        ttl_seconds: float = 300.0,
        now: float | None = None,
    ) -> RecoveryLease:
        if not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be finite and positive")
        t = time.time() if now is None else float(now)
        if not math.isfinite(t):
            raise ValueError("recovery lease observation time must be finite")
        with self._guard:
            current = self.read()
            if (
                current is None
                or current.owner_id != owner_id
                or current.manifest_digest != manifest_digest
                or current.expires_at <= t
            ):
                raise RecoveryLeaseBusy("runtime recovery lease cannot be renewed by this owner/manifest")
            renewed = RecoveryLease(current.owner_id, current.manifest_digest, current.acquired_at, t + ttl_seconds)
            atomic_replace_bytes(self.path, self.codec.encode(renewed))
            return renewed

    def assert_owned(
        self,
        owner_id: str,
        manifest_digest: str,
        *,
        now: float | None = None,
    ) -> RecoveryLease:
        t = time.time() if now is None else float(now)
        if not math.isfinite(t):
            raise ValueError("recovery lease observation time must be finite")
        with self._guard:
            lease = self.read()
            if (
                lease is None
                or lease.owner_id != owner_id
                or lease.manifest_digest != manifest_digest
                or lease.expires_at <= t
            ):
                raise RecoveryLeaseBusy("runtime recovery lease not held")
            return lease

    def release(self, owner_id: str, manifest_digest: str) -> None:
        with self._guard:
            lease = self.read()
            if lease is None:
                return
            if lease.owner_id != owner_id or lease.manifest_digest != manifest_digest:
                raise RecoveryLeaseBusy(
                    "cannot release runtime recovery lease owned by a different owner/manifest"
                )
            durable_unlink(self.path)


__all__ = ["RecoveryLeaseStore"]
