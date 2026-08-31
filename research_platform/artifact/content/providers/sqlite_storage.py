from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from research_platform.artifact._sqlite_connection import (
    connect_artifact_reader,
    connect_artifact_writer,
    rollback_artifact_writer,
)
from research_platform.artifact._sqlite_types import require_text
from research_platform.artifact.content.api import (
    ArtifactStorageBinding,
    ArtifactStorageBindingConflict,
    ArtifactStorageBindingCorruptionError,
    ArtifactStorageBindingNotFound,
)
from research_platform.platform.kernel import canonical_digest


class SQLiteArtifactStorageBindingStore:
    """Durable CAS authority for physical artifact storage placement."""

    _COLUMNS = (
        "artifact_id", "content_sha256", "storage_provider_id",
        "location", "generation", "record_sha256",
    )

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect_writer()) as db:
            self._ensure_schema(db)

    def _connect_writer(self) -> sqlite3.Connection:
        return connect_artifact_writer(self.path, timeout_seconds=self.timeout_seconds)

    def _connect_reader(self) -> sqlite3.Connection:
        return connect_artifact_reader(self.path, timeout_seconds=self.timeout_seconds)

    @classmethod
    def _ensure_schema(cls, db: sqlite3.Connection) -> None:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS artifact_storage_bindings(
                artifact_id TEXT PRIMARY KEY,
                content_sha256 TEXT NOT NULL,
                storage_provider_id TEXT NOT NULL,
                location TEXT NOT NULL,
                generation INTEGER NOT NULL,
                record_sha256 TEXT NOT NULL
            )
            """
        )
        columns = tuple(
            row[1] for row in db.execute("PRAGMA table_info(artifact_storage_bindings)")
        )
        if columns != cls._COLUMNS:
            raise ArtifactStorageBindingCorruptionError(
                f"unsupported artifact storage schema columns: {columns!r}"
            )

    @staticmethod
    def _document(binding: ArtifactStorageBinding) -> dict[str, object]:
        return {
            "artifact_id": binding.artifact_id,
            "content_sha256": binding.content_sha256,
            "storage_provider_id": binding.storage_provider_id,
            "location": binding.location,
            "generation": binding.generation,
        }

    @classmethod
    def _record_digest(cls, binding: ArtifactStorageBinding) -> str:
        return canonical_digest(cls._document(binding))

    @classmethod
    def _encode(cls, binding: ArtifactStorageBinding) -> tuple[object, ...]:
        return (
            binding.artifact_id,
            binding.content_sha256,
            binding.storage_provider_id,
            binding.location,
            binding.generation,
            cls._record_digest(binding),
        )

    @classmethod
    def _decode(cls, row: tuple[object, ...]) -> ArtifactStorageBinding:
        try:
            generation = row[4]
            if isinstance(generation, bool) or not isinstance(generation, int):
                raise TypeError("artifact storage generation must be an integer")
            binding = ArtifactStorageBinding(
                artifact_id=require_text(row[0], label="artifact storage artifact_id"),
                content_sha256=require_text(row[1], label="artifact storage content_sha256"),
                storage_provider_id=require_text(row[2], label="artifact storage provider_id"),
                location=require_text(row[3], label="artifact storage location"),
                generation=generation,
            )
            stored_digest = require_text(row[5], label="artifact storage record_sha256")
        except (IndexError, TypeError, ValueError) as exc:
            raise ArtifactStorageBindingCorruptionError(
                "artifact storage binding cannot be decoded"
            ) from exc
        if cls._record_digest(binding) != stored_digest:
            raise ArtifactStorageBindingCorruptionError(
                f"artifact storage binding integrity mismatch: {binding.artifact_id}"
            )
        return binding

    @classmethod
    def _select_columns(cls) -> str:
        return ",".join(cls._COLUMNS)

    def bind(
        self,
        *,
        artifact_id: str,
        content_sha256: str,
        storage_provider_id: str,
        location: str,
    ) -> ArtifactStorageBinding:
        proposed = ArtifactStorageBinding(
            artifact_id=artifact_id,
            content_sha256=content_sha256,
            storage_provider_id=storage_provider_id,
            location=location,
            generation=1,
        )
        with closing(self._connect_writer()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    f"SELECT {self._select_columns()} FROM artifact_storage_bindings WHERE artifact_id=?",
                    (artifact_id,),
                ).fetchone()
                if row is not None:
                    current = self._decode(row)
                    if current == proposed:
                        db.execute("COMMIT")
                        return current
                    raise ArtifactStorageBindingConflict(artifact_id)
                db.execute(
                    "INSERT INTO artifact_storage_bindings VALUES(?,?,?,?,?,?)",
                    self._encode(proposed),
                )
                db.execute("COMMIT")
            except BaseException as primary:
                rollback_artifact_writer(db, primary)
                raise
        return proposed

    def resolve(self, artifact_id: str) -> ArtifactStorageBinding:
        if not artifact_id.strip():
            raise ValueError("artifact storage lookup identity must be non-empty")
        with closing(self._connect_reader()) as db:
            row = db.execute(
                f"SELECT {self._select_columns()} FROM artifact_storage_bindings WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise ArtifactStorageBindingNotFound(artifact_id)
        return self._decode(row)

    def relocate(
        self,
        artifact_id: str,
        *,
        expected_generation: int,
        storage_provider_id: str,
        location: str,
    ) -> ArtifactStorageBinding:
        if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation <= 0:
            raise ValueError("expected_generation must be a positive integer")
        if not storage_provider_id.strip() or not location.strip():
            raise ValueError("artifact storage provider/location must be non-empty")
        with closing(self._connect_writer()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    f"SELECT {self._select_columns()} FROM artifact_storage_bindings WHERE artifact_id=?",
                    (artifact_id,),
                ).fetchone()
                if row is None:
                    raise ArtifactStorageBindingNotFound(artifact_id)
                current = self._decode(row)
                if current.generation != expected_generation:
                    raise ArtifactStorageBindingConflict(
                        f"{artifact_id}: expected generation {expected_generation}, got {current.generation}"
                    )
                if (
                    current.storage_provider_id == storage_provider_id
                    and current.location == location
                ):
                    db.execute("COMMIT")
                    return current
                updated = ArtifactStorageBinding(
                    artifact_id=current.artifact_id,
                    content_sha256=current.content_sha256,
                    storage_provider_id=storage_provider_id,
                    location=location,
                    generation=current.generation + 1,
                )
                cursor = db.execute(
                    "UPDATE artifact_storage_bindings SET content_sha256=?,storage_provider_id=?,location=?,generation=?,record_sha256=? WHERE artifact_id=? AND generation=?",
                    (
                        updated.content_sha256,
                        updated.storage_provider_id,
                        updated.location,
                        updated.generation,
                        self._record_digest(updated),
                        updated.artifact_id,
                        expected_generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ArtifactStorageBindingConflict(
                        f"{artifact_id}: storage generation changed during relocation"
                    )
                db.execute("COMMIT")
            except BaseException as primary:
                rollback_artifact_writer(db, primary)
                raise
        return updated


__all__ = ["SQLiteArtifactStorageBindingStore"]