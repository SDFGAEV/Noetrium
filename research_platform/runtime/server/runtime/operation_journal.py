from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
from contextlib import AbstractContextManager

from research_platform.platform.kernel import canonical_bytes
from research_platform.platform.kernel.durability import fsync_directory
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock
from research_platform.platform.kernel.durability.file_lock import InterprocessLockBusy
from research_platform.platform.concurrency.api import SerialActorPort
from research_platform.runtime.server.api import (
    ServerOperationEffect,
    ServerOperationFinished,
    ServerOperationJournalPort,
    ServerOperationStarted,
    ServerOperationKind,
    ServerOperationRecord,
    ServerOperationResolved,
    ServerOperationResolution,
    ServerOperationState,
    ServerOperationTransitionConflict,
    ServerMutationBusy,
    ServerTransportBusy,
)


class ServerOperationJournalIntegrityError(RuntimeError):
    """The durable server-operation ledger cannot be safely replayed."""


_JOURNAL_SCHEMA = "server-operation-journal.v2"
_GENESIS_CHECKSUM = "0" * 64
_MAX_RECORD_BYTES = 256 * 1024
_CHECKSUM_RE = re.compile(r"[0-9a-f]{64}")


def _record_checksum(body: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


class _NonBlockingServerLock(AbstractContextManager[object]):
    """Translate a non-blocking kernel lock into a server-domain failure."""

    def __init__(self, path: Path, *, server_id: str, busy_error: type[RuntimeError]) -> None:
        self.path = path
        self._lock = InterprocessFileLock(path, blocking=False)
        self._server_id = server_id
        self._busy_error = busy_error

    def __enter__(self) -> object:
        try:
            return self._lock.__enter__()
        except InterprocessLockBusy as exc:
            raise self._busy_error(self._server_id) from exc

    def __exit__(self, exc_type, exc, tb) -> None:
        self._lock.__exit__(exc_type, exc, tb)


class _NonBlockingOperationLock(AbstractContextManager[object]):
    """Fence transitions for one operation without serializing unrelated operations."""

    def __init__(self, path: Path, *, operation_id: str) -> None:
        self.path = path
        self._operation_id = operation_id
        self._lock = InterprocessFileLock(path, blocking=False)

    def __enter__(self) -> object:
        try:
            return self._lock.__enter__()
        except InterprocessLockBusy as exc:
            raise ServerOperationTransitionConflict(
                self._operation_id, "another transition is in progress"
            ) from exc

    def __exit__(self, exc_type, exc, tb) -> None:
        self._lock.__exit__(exc_type, exc, tb)


class JsonlServerOperationJournal(ServerOperationJournalPort):
    """Append-only local operation ledger for server control-plane actions.

    The ledger is controller-local and contains no credentials or raw remote
    commands.  It stores correlation IDs, request digests, timing, result
    classes and bounded output sizes, so a failed SSH operation can be
    diagnosed without making the server profile or command text a secret
    transport.
    """

    def __init__(self, path: str | Path, *, writer_actor: SerialActorPort) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._guard_path = self.path.with_name(self.path.name + ".guard.lock")
        self._writer_actor = writer_actor

    def _operation_transition_lock(
        self, operation_id: str
    ) -> AbstractContextManager[object]:
        if not operation_id:
            raise ValueError("operation_id must be non-empty")
        identity = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
        return _NonBlockingOperationLock(
            self.path.with_name(f"{self.path.name}.{identity}.transition.lock"),
            operation_id=operation_id,
        )

    @staticmethod
    def _decode_envelope(
        raw: bytes,
        *,
        expected_previous_checksum: str | None,
    ) -> tuple[dict[str, object], str]:
        if not raw or len(raw) > _MAX_RECORD_BYTES:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger record size is invalid"
            )
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger record is not canonical JSON"
            ) from exc
        if not isinstance(document, dict):
            raise ServerOperationJournalIntegrityError(
                "server operation ledger record is not an object"
            )
        record_checksum = document.get("record_checksum")
        previous_checksum = document.get("previous_checksum")
        if document.get("journal_schema") != _JOURNAL_SCHEMA:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger schema is unsupported"
            )
        if not isinstance(record_checksum, str) or _CHECKSUM_RE.fullmatch(record_checksum) is None:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger record checksum is invalid"
            )
        if not isinstance(previous_checksum, str) or _CHECKSUM_RE.fullmatch(previous_checksum) is None:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger previous checksum is invalid"
            )
        if (
            expected_previous_checksum is not None
            and previous_checksum != expected_previous_checksum
        ):
            raise ServerOperationJournalIntegrityError(
                "server operation ledger hash chain is discontinuous"
            )
        body = dict(document)
        body.pop("record_checksum", None)
        if _record_checksum(body) != record_checksum:
            raise ServerOperationJournalIntegrityError(
                "server operation ledger record checksum mismatch"
            )
        body.pop("journal_schema", None)
        body.pop("previous_checksum", None)
        return body, record_checksum

    def _tail_checksum_locked(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return _GENESIS_CHECKSUM
        with self.path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            end = stream.tell()
            stream.seek(end - 1)
            if stream.read(1) != b"\n":
                raise ServerOperationJournalIntegrityError(
                    "server operation ledger has a partial durable tail"
                )
            cursor = end - 1
            chunks: list[bytes] = []
            scanned = 0
            while cursor > 0:
                block_start = max(0, cursor - 4096)
                stream.seek(block_start)
                block = stream.read(cursor - block_start)
                split = block.rfind(b"\n")
                if split >= 0:
                    chunks.insert(0, block[split + 1 :])
                    break
                chunks.insert(0, block)
                scanned += len(block)
                if scanned > _MAX_RECORD_BYTES:
                    raise ServerOperationJournalIntegrityError(
                        "server operation ledger tail record is oversized"
                    )
                cursor = block_start
            raw = b"".join(chunks)
            _body, checksum = self._decode_envelope(
                raw,
                expected_previous_checksum=None,
            )
            return checksum

    def _append(self, event_type: str, event: object) -> None:
        """Append one hash-chained event and durably publish its first directory entry."""
        payload = asdict(event)
        for key, value in tuple(payload.items()):
            if hasattr(value, "value"):
                payload[key] = value.value
        validator = {
            "started": self._started,
            "finished": self._finished,
            "resolved": self._resolved,
        }.get(event_type)
        if validator is None:
            raise ValueError(f"unsupported server operation event type: {event_type!r}")
        validator(dict(payload))

        def append_owned() -> None:
            with InterprocessFileLock(self._guard_path):
                previous_checksum = self._tail_checksum_locked()
                body = {
                    "journal_schema": _JOURNAL_SCHEMA,
                    "previous_checksum": previous_checksum,
                    "event": event_type,
                    **payload,
                }
                record = {**body, "record_checksum": _record_checksum(body)}
                encoded = canonical_bytes(record) + b"\n"
                if len(encoded) > _MAX_RECORD_BYTES:
                    raise ValueError("server operation journal record exceeds size limit")
                created = not self.path.exists()
                with self.path.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                if created:
                    fsync_directory(self.path.parent)

        self._writer_actor.call(f"append:{event_type}", append_owned)

    @staticmethod
    def _started(payload: dict[str, object]) -> ServerOperationStarted:
        expected = {
            "operation_id", "server_id", "kind", "request_digest", "started_at",
            "interactive", "profile_digest", "effect",
        }
        try:
            if set(payload) != expected:
                raise ValueError("started field set is not exact")
            for key in ("operation_id", "server_id", "kind", "request_digest", "profile_digest", "effect"):
                if type(payload[key]) is not str:
                    raise TypeError(f"{key} must be a string")
            if type(payload["interactive"]) is not bool:
                raise TypeError("interactive must be a boolean")
            started_at = payload["started_at"]
            if type(started_at) not in {int, float} or isinstance(started_at, bool) or not math.isfinite(float(started_at)) or float(started_at) < 0:
                raise ValueError("started_at must be a finite non-negative number")
            return ServerOperationStarted(
                payload["operation_id"], payload["server_id"], ServerOperationKind(payload["kind"]),
                payload["request_digest"], float(started_at), payload["interactive"],
                payload["profile_digest"], ServerOperationEffect(payload["effect"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation started record is malformed"
            ) from exc

    @staticmethod
    def _finished(payload: dict[str, object]) -> ServerOperationFinished:
        expected = {
            "operation_id", "server_id", "kind", "request_digest", "state",
            "finished_at", "duration_seconds", "return_code", "failure_kind",
            "stdout_bytes", "stderr_bytes", "error_type", "error_digest",
            "profile_digest", "stdout_digest", "stderr_digest", "effect",
            "stdout_preview", "stderr_preview",
        }
        try:
            if set(payload) != expected:
                raise ValueError("finished field set is not exact")
            string_keys = (
                "operation_id", "server_id", "kind", "request_digest", "state",
                "failure_kind", "profile_digest", "stdout_digest", "stderr_digest",
                "effect", "stdout_preview", "stderr_preview",
            )
            if any(type(payload[key]) is not str for key in string_keys):
                raise TypeError("finished string field has wrong type")
            for key in ("error_type", "error_digest"):
                if payload[key] is not None and type(payload[key]) is not str:
                    raise TypeError(f"{key} must be null or string")
            for key in ("finished_at", "duration_seconds"):
                value = payload[key]
                if type(value) not in {int, float} or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
                    raise ValueError(f"{key} must be finite and non-negative")
            for key in ("stdout_bytes", "stderr_bytes"):
                if type(payload[key]) is not int or payload[key] < 0:
                    raise ValueError(f"{key} must be a non-negative integer")
            if payload["return_code"] is not None and type(payload["return_code"]) is not int:
                raise TypeError("return_code must be null or integer")
            return ServerOperationFinished(
                payload["operation_id"], payload["server_id"], ServerOperationKind(payload["kind"]),
                payload["request_digest"], ServerOperationState(payload["state"]),
                float(payload["finished_at"]), float(payload["duration_seconds"]),
                payload["return_code"], payload["failure_kind"], payload["stdout_bytes"],
                payload["stderr_bytes"], payload["error_type"], payload["error_digest"],
                payload["profile_digest"], payload["stdout_digest"], payload["stderr_digest"],
                ServerOperationEffect(payload["effect"]), payload["stdout_preview"], payload["stderr_preview"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation finished record is malformed"
            ) from exc

    @staticmethod
    def _resolved(payload: dict[str, object]) -> ServerOperationResolved:
        expected = {
            "operation_id", "server_id", "kind", "request_digest", "disposition",
            "resolved_at", "evidence_ref", "evidence_digest", "profile_digest",
        }
        try:
            if set(payload) != expected:
                raise ValueError("resolution field set is not exact")
            for key in (
                "operation_id", "server_id", "kind", "request_digest", "disposition",
                "evidence_ref", "evidence_digest", "profile_digest",
            ):
                if type(payload[key]) is not str:
                    raise TypeError(f"{key} must be a string")
            resolved_at = payload["resolved_at"]
            if type(resolved_at) not in {int, float} or isinstance(resolved_at, bool) or not math.isfinite(float(resolved_at)) or float(resolved_at) < 0:
                raise ValueError("resolved_at must be finite and non-negative")
            evidence_ref = payload["evidence_ref"]
            evidence_digest = payload["evidence_digest"]
            if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", evidence_ref) is None:
                raise ValueError("resolution evidence reference is unsafe")
            if re.fullmatch(r"[0-9a-f]{64}", evidence_digest) is None:
                raise ValueError("resolution evidence digest is not canonical SHA-256")
            return ServerOperationResolved(
                payload["operation_id"], payload["server_id"], ServerOperationKind(payload["kind"]),
                payload["request_digest"], ServerOperationResolution(payload["disposition"]),
                float(resolved_at), evidence_ref, evidence_digest, payload["profile_digest"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation resolution record is malformed"
            ) from exc

    def _read_records(self) -> tuple[ServerOperationRecord, ...]:
        """Read one rotation-free and append-free journal snapshot.

        Replay freezes one durable byte prefix through the writer actor and
        validates that immutable prefix outside the writer authority.
        """
        if not self.path.exists():
            return ()
        records: dict[str, ServerOperationRecord] = {}
        order: list[str] = []
        # Freeze only the durable byte boundary under the writer authority.  The
        # journal never rotates, so subsequent appends can only extend this prefix.
        # Parsing the frozen prefix outside the lock removes O(file-size) lock hold.
        def freeze_owned() -> int:
            with InterprocessFileLock(self._guard_path):
                return self.path.stat().st_size

        snapshot_size = self._writer_actor.call("freeze-read-prefix", freeze_owned)
        expected_previous_checksum = _GENESIS_CHECKSUM
        with self.path.open("rb") as stream:
            remaining = snapshot_size
            line_number = 0
            while remaining > 0:
                raw = stream.readline(remaining)
                if not raw:
                    break
                remaining -= len(raw)
                line_number += 1
                try:
                    if not raw.endswith(b"\n"):
                        raise ServerOperationJournalIntegrityError(
                            "server operation ledger has a partial durable tail"
                        )
                    payload, record_checksum = self._decode_envelope(
                        raw[:-1],
                        expected_previous_checksum=expected_previous_checksum,
                    )
                    expected_previous_checksum = record_checksum
                    event_type = payload.pop("event")
                    if event_type == "started":
                        event = self._started(payload)
                        if event.operation_id in records:
                            raise ValueError("duplicate operation start")
                        records[event.operation_id] = ServerOperationRecord(event)
                        order.append(event.operation_id)
                    elif event_type == "finished":
                        event = self._finished(payload)
                        record = records.get(event.operation_id)
                        if (
                            record is None
                            or record.finished is not None
                            or record.resolution is not None
                        ):
                            raise ValueError("finish has no unique open operation")
                        if event.state is ServerOperationState.STARTED:
                            raise ValueError("finished event cannot use started state")
                        if (
                            record.started.server_id != event.server_id
                            or record.started.kind != event.kind
                            or record.started.request_digest != event.request_digest
                            or record.started.profile_digest != event.profile_digest
                            or record.started.effect != event.effect
                        ):
                            raise ValueError("finish does not match its start")
                        records[event.operation_id] = ServerOperationRecord(
                            record.started, event, record.resolution
                        )
                    elif event_type == "resolved":
                        event = self._resolved(payload)
                        record = records.get(event.operation_id)
                        if record is None or record.resolution is not None:
                            raise ValueError("resolution has no unique open operation")
                        if (
                            record.started.server_id != event.server_id
                            or record.started.kind != event.kind
                            or record.started.request_digest != event.request_digest
                            or record.started.profile_digest != event.profile_digest
                        ):
                            raise ValueError("resolution does not match its start")
                        if not record.effect_uncertain:
                            raise ValueError("resolution is only valid for an uncertain operation")
                        records[event.operation_id] = ServerOperationRecord(
                            record.started, record.finished, event
                        )
                    else:
                        raise ValueError(f"unknown event type {event_type!r}")
                except ServerOperationJournalIntegrityError as exc:
                    raise ServerOperationJournalIntegrityError(
                        f"server operation ledger is corrupt at line {line_number}: {exc}"
                    ) from exc
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                    raise ServerOperationJournalIntegrityError(
                        f"server operation ledger is corrupt at line {line_number}: {exc}"
                    ) from exc
        return tuple(records[operation_id] for operation_id in order)

    def record_started(self, event: ServerOperationStarted) -> None:
        with self._operation_transition_lock(event.operation_id):
            if self.read_operation(event.operation_id) is not None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "operation is already recorded"
                )
            self._append("started", event)

    def record_finished(self, event: ServerOperationFinished) -> None:
        with self._operation_transition_lock(event.operation_id):
            record = self.read_operation(event.operation_id)
            if record is None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "finish has no recorded start"
                )
            if record.finished is not None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "operation is already finished"
                )
            if record.resolution is not None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "operation was already reconciled"
                )
            if event.state is ServerOperationState.STARTED:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "finished event cannot use started state"
                )
            started = record.started
            if (
                started.server_id != event.server_id
                or started.kind != event.kind
                or started.request_digest != event.request_digest
                or started.profile_digest != event.profile_digest
                or started.effect != event.effect
            ):
                raise ServerOperationTransitionConflict(
                    event.operation_id, "finish identity does not match its start"
                )
            self._append("finished", event)

    def record_resolved(self, event: ServerOperationResolved) -> None:
        with self._operation_transition_lock(event.operation_id):
            record = self.read_operation(event.operation_id)
            if record is None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "resolution has no recorded operation"
                )
            if record.resolution is not None:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "operation is already reconciled"
                )
            if (
                record.server_id != event.server_id
                or record.kind != event.kind
                or record.started.request_digest != event.request_digest
                or record.started.profile_digest != event.profile_digest
            ):
                raise ServerOperationTransitionConflict(
                    event.operation_id, "resolution identity does not match its start"
                )
            if not record.effect_uncertain:
                raise ServerOperationTransitionConflict(
                    event.operation_id, "operation does not require reconciliation"
                )
            self._append("resolved", event)

    def mutation_lock(self, *, server_id: str) -> AbstractContextManager[object]:
        """Serialize mutating remote operations for one logical server.

        The lock is deliberately separate from the short ledger append lock:
        it remains held across the remote operation, so two controllers cannot
        concurrently prepare/upload/terminate the same server state while both
        still observe an empty pending set. Process exit releases the kernel
        lock; the durable ledger then records the interrupted operation as
        effect-uncertain for the next controller.
        """

        if not server_id:
            raise ValueError("server_id must be non-empty")
        identity = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:32]
        return _NonBlockingServerLock(
            self.path.with_name(f"{self.path.name}.{identity}.mutation.lock"),
            server_id=server_id,
            busy_error=ServerMutationBusy,
        )

    def transport_lock(self, *, server_id: str) -> AbstractContextManager[object]:
        """Serialize every SSH/SCP attempt for one logical server.

        This is deliberately separate from the mutation lock.  A read-only
        health/status probe must not race an in-flight mutation into a shared
        SSH authentication or ControlMaster channel, but it also must not
        participate in mutation-effect reconciliation.
        """

        if not server_id:
            raise ValueError("server_id must be non-empty")
        identity = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:32]
        return _NonBlockingServerLock(
            self.path.with_name(f"{self.path.name}.{identity}.transport.lock"),
            server_id=server_id,
            busy_error=ServerTransportBusy,
        )

    def read_operation(self, operation_id: str) -> ServerOperationRecord | None:
        if not operation_id:
            raise ValueError("operation_id must be non-empty")
        return next(
            (record for record in self._read_records() if record.operation_id == operation_id),
            None,
        )

    def pending_operations(
        self,
        *,
        server_id: str | None = None,
    ) -> tuple[ServerOperationRecord, ...]:
        """Return operations whose remote effect is not durably known.

        This is a reconciliation signal, not a retry queue.  A caller must
        inspect the remote effect and record a resolution before submitting a
        mutating operation again.
        """

        return tuple(
            record
            for record in self._read_records()
            if record.effect_uncertain
            and (server_id is None or record.server_id == server_id)
        )

    def recent_operations(
        self,
        limit: int = 20,
        *,
        server_id: str | None = None,
    ) -> tuple[ServerOperationRecord, ...]:
        if limit <= 0:
            raise ValueError("operation history limit must be positive")
        records = tuple(
            record
            for record in self._read_records()
            if server_id is None or record.server_id == server_id
        )
        return tuple(reversed(records[-limit:]))


__all__ = ["JsonlServerOperationJournal", "ServerOperationJournalIntegrityError"]
