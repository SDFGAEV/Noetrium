from __future__ import annotations

"""Durable append-only structured log storage.

The logging system owns records and queries; this adapter owns only the
storage protocol.  Each append is a complete JSON line followed by an fsync,
so a restart can recover every complete record without reconstructing an
in-memory log from the application process.
"""

import heapq
import json
import os
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.platform.kernel.durability.durable_file import durable_replace_file, durable_unlink, fsync_directory
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock
from research_platform.platform.kernel.logical_path import logical_absolute_path
from research_platform.observability.logging.storage.api import LogStorageWriteActorPort

from .codec import LOG_RECORD_SCHEMA_VERSION, decode_log_line, encode_log_record


class JsonlLogCorruptionError(ValueError):
    """A complete JSONL record is corrupt and cannot be safely ignored."""


class JsonlLogStore:
    """Crash-tolerant structured log store with deterministic query order."""

    SCHEMA_VERSION: ClassVar[str] = LOG_RECORD_SCHEMA_VERSION

    @staticmethod
    def logical_path(path: str | Path) -> Path:
        return logical_absolute_path(path, expand_user=True)

    def __init__(self, path: str | Path, *, writer_actor: LogStorageWriteActorPort, max_bytes: int = 64 * 1024 * 1024, max_segments: int = 8) -> None:
        if max_bytes <= 0:
            raise ValueError("JSONL log max_bytes must be positive")
        if max_segments <= 0:
            raise ValueError("JSONL log max_segments must be positive")
        self.path = self.logical_path(path)
        self.max_bytes = max_bytes
        self.max_segments = max_segments
        self._writer_actor = writer_actor
        self._guard_path = self.path.with_name(self.path.name + ".guard.lock")
        self._last_query_diagnostics: dict[str, int | bool] = {
            "corrupt_complete_lines": 0,
            "partial_tail_ignored": False,
            "scanned_lines": 0,
            "rotated_segments": 0,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last_query_diagnostics(self) -> dict[str, int | bool]:
        return dict(self._last_query_diagnostics)

    def append(self, record: LogRecord) -> None:
        encoded = (
            json.dumps(
                encode_log_record(record),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

        def append_owned() -> None:
            with InterprocessFileLock(self._guard_path):
                self._rotate_if_needed(len(encoded))
                self._append_record(encoded)

        self._writer_actor.call("append", append_owned)

    _SEGMENT_MARKER: ClassVar[str] = ".segment."
    _SEGMENT_DIGITS: ClassVar[int] = 20

    def _rotated_segment_entries(self) -> tuple[tuple[int, Path], ...]:
        prefix = self.path.name + self._SEGMENT_MARKER
        rotated: list[tuple[int, Path]] = []
        seen: set[int] = set()
        for path in self.path.parent.glob(prefix + "*"):
            suffix = path.name[len(prefix):]
            parts = suffix.split(".")
            if len(parts) != 2:
                raise JsonlLogCorruptionError(
                    f"malformed immutable JSONL segment generation: {path}"
                )
            generation_text, uniqueness = parts
            if (
                len(generation_text) != self._SEGMENT_DIGITS
                or not generation_text.isdigit()
                or len(uniqueness) != 32
                or uniqueness.lower() != uniqueness
                or any(character not in "0123456789abcdef" for character in uniqueness)
            ):
                raise JsonlLogCorruptionError(
                    f"malformed immutable JSONL segment generation: {path}"
                )
            generation = int(generation_text)
            if generation <= 0 or generation in seen:
                raise JsonlLogCorruptionError(
                    f"duplicate or invalid immutable JSONL segment generation: {path}"
                )
            if not path.is_file():
                raise JsonlLogCorruptionError(
                    f"immutable JSONL segment is not a regular file: {path}"
                )
            seen.add(generation)
            rotated.append((generation, path))
        rotated.sort(key=lambda item: item[0], reverse=True)
        return tuple(rotated)

    def _segments(self) -> tuple[Path, ...]:
        return (self.path, *(path for _, path in self._rotated_segment_entries()))

    def _next_generation(self) -> int:
        entries = self._rotated_segment_entries()
        generation = (entries[0][0] + 1) if entries else 1
        if generation >= 10 ** self._SEGMENT_DIGITS:
            raise RuntimeError("JSONL immutable segment generation exhausted")
        return generation

    def _segment_path(self, generation: int) -> Path:
        return self.path.with_name(
            f"{self.path.name}{self._SEGMENT_MARKER}"
            f"{generation:0{self._SEGMENT_DIGITS}d}.{uuid4().hex}"
        )

    def _prune_rotated_segments(self) -> None:
        entries = self._rotated_segment_entries()
        for _, stale in entries[self.max_segments:]:
            durable_unlink(stale)

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.is_file() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        generation = self._next_generation()
        destination = self._segment_path(generation)
        if destination.exists():
            raise JsonlLogCorruptionError(
                f"immutable JSONL generation already exists: {destination}"
            )

        # Publication is one durable rename.  Only after that rename is durable
        # may retention prune older immutable generations.  A crash before the
        # rename leaves the active file intact; a crash after it can only leave
        # extra retained history, never a missing newest generation.
        durable_replace_file(self.path, destination)
        self._prune_rotated_segments()

    def _append_record(self, encoded: bytes) -> None:
        existed = self.path.exists()
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if not existed:
            fsync_directory(self.path.parent)

    def _freeze_query_snapshot(self) -> tuple[tuple[Path, int, int, int], ...]:
        """Freeze path identities/boundaries on the writer actor, then scan lock-free."""

        def freeze_owned() -> tuple[tuple[Path, int, int, int], ...]:
            with InterprocessFileLock(self._guard_path):
                frozen: list[tuple[Path, int, int, int]] = []
                for path in self._segments():
                    if not path.is_file():
                        continue
                    stat = path.stat()
                    frozen.append((path, int(stat.st_dev), int(stat.st_ino), int(stat.st_size)))
                return tuple(frozen)

        return self._writer_actor.call("freeze-query-snapshot", freeze_owned)

    @staticmethod
    def _iter_frozen_lines(
        snapshot: tuple[tuple[Path, int, int, int], ...],
    ):
        """Read only bytes covered by a frozen snapshot, with no writer lock held."""

        for segment, expected_dev, expected_ino, limit_bytes in snapshot:
            try:
                with segment.open("rb") as handle:
                    opened = os.fstat(handle.fileno())
                    if int(opened.st_dev) != expected_dev or int(opened.st_ino) != expected_ino:
                        raise FileNotFoundError(f"log segment identity changed: {segment}")
                    consumed = 0
                    line_number = 0
                    while consumed < limit_bytes:
                        raw = handle.readline(limit_bytes - consumed)
                        if not raw:
                            break
                        consumed += len(raw)
                        line_number += 1
                        yield segment, line_number, raw
            except FileNotFoundError:
                raise

    def query(
        self,
        *,
        scope: ScopeIdentity | None = None,
        system: SystemIdentity | None = None,
        component_id: str | None = None,
        trace_id: str | None = None,
        level_at_least: LogLevel | None = None,
        event: str | None = None,
        limit: int = 1000,
    ) -> tuple[LogRecord, ...]:
        """Query a bounded immutable byte snapshot without holding writer locks during I/O.

        The guard freezes segment identities and byte boundaries only.  Parsing and
        filtering occur lock-free.  If rotation wins between freeze and open, the
        query retries from a new snapshot instead of mixing generations.
        """
        if limit <= 0:
            return ()
        rank = {level: index for index, level in enumerate(LogLevel)}
        last_identity_error: OSError | None = None
        for _attempt in range(4):
            snapshot = self._freeze_query_snapshot()
            if not snapshot:
                return ()
            selected: list[tuple[tuple[float, str, int], LogRecord]] = []
            corrupt_complete_lines = 0
            partial_tail_ignored = False
            scanned_lines = 0
            try:
                for segment, line_number, raw in self._iter_frozen_lines(snapshot):
                    scanned_lines += 1
                    if not raw.strip():
                        continue
                    complete = raw.endswith(b"\n")
                    try:
                        line = raw.decode("utf-8")
                        row = decode_log_line(line)
                    except (UnicodeDecodeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                        if not complete:
                            partial_tail_ignored = True
                            continue
                        corrupt_complete_lines += 1
                        raise JsonlLogCorruptionError(
                            f"corrupt complete JSONL record at line {line_number}: {segment}"
                        )
                    address = row.address
                    if scope is not None and scope not in address.scope_path:
                        continue
                    if system is not None and system not in address.system_path:
                        continue
                    if component_id is not None and address.component_id != component_id:
                        continue
                    if trace_id is not None and address.trace_id != trace_id:
                        continue
                    if level_at_least is not None and rank[row.level] < rank[level_at_least]:
                        continue
                    if event is not None and row.event != event:
                        continue
                    key = (row.created_at, row.log_id, scanned_lines)
                    item = (key, row)
                    if len(selected) < limit:
                        heapq.heappush(selected, item)
                    elif key > selected[0][0]:
                        heapq.heapreplace(selected, item)
            except FileNotFoundError as exc:
                last_identity_error = exc
                continue
            except PermissionError as exc:
                if os.name != "nt":
                    raise
                last_identity_error = exc
                continue

            self._last_query_diagnostics = {
                "corrupt_complete_lines": corrupt_complete_lines,
                "partial_tail_ignored": partial_tail_ignored,
                "scanned_lines": scanned_lines,
                "rotated_segments": sum(
                    1 for segment, *_ in snapshot if segment != self.path
                ),
            }
            rows = [item[1] for item in selected]
            rows.sort(key=lambda row: (row.created_at, row.log_id), reverse=True)
            return tuple(rows)
        raise RuntimeError("log query could not freeze a stable segment generation") from last_identity_error


__all__ = ["JsonlLogCorruptionError", "JsonlLogStore"]
