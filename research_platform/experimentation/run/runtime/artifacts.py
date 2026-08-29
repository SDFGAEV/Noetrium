from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from research_platform.platform.kernel import JsonObject, JsonValue, canonical_bytes, canonical_digest

from .diagnostics import json_default
from ..api.artifacts import (
    RunArtifactFinalizationError,
    RunArtifactKind,
    RunArtifactSnapshotReceipt,
    RunArtifactStorePort,
    RunArtifactVerificationError,
    RunArtifactWriteActorPort,
)

_FINALIZED_DIR = ".run-artifact-finalized"


class DirectoryRunArtifactStore(RunArtifactStorePort):
    """Crash-safe run-local artifact authority with finalized snapshot receipts."""

    def __init__(
        self,
        root: Path | str,
        *,
        run_id: str,
        writer_actor: RunArtifactWriteActorPort,
    ) -> None:
        if type(run_id) is not str or not run_id.strip() or "/" in run_id or "\\" in run_id:
            raise ValueError("run artifact store run_id must be a non-empty identity")
        self.root = Path(root).expanduser().resolve()
        self.run_id = run_id
        self._writer_actor = writer_actor

    def _resolve_ref(self, name: str, *, create_parent: bool) -> Path:
        if type(name) is not str or not name.strip() or "\\" in name or Path(name).is_absolute():
            raise ValueError("run artifact name must be a non-empty run-local path")
        parts = name.split("/")
        if any(not part or part in {".", ".."} for part in parts):
            raise ValueError("run artifact name contains an unsafe path component")
        if parts[0] == _FINALIZED_DIR:
            raise ValueError("run artifact name uses a reserved authority path")
        target = (self.root / Path(*parts)).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("run artifact path escapes the run root") from exc
        if create_parent:
            target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def path(self, name: str, *, kind: RunArtifactKind) -> str:
        if type(kind) is not RunArtifactKind:
            raise ValueError("run artifact kind must be RunArtifactKind")
        return str(self._resolve_ref(name, create_parent=True))

    def directory(self, name: str, *, kind: RunArtifactKind) -> str:
        if type(kind) is not RunArtifactKind:
            raise ValueError("run artifact kind must be RunArtifactKind")
        target = self._resolve_ref(name, create_parent=False)
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def publish_json(self, name: str, payload: JsonValue, *, kind: RunArtifactKind) -> str:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n"
        return self.publish_text(name, body, kind=kind)

    def publish_text(self, name: str, content: str, *, kind: RunArtifactKind) -> str:
        target = self._resolve_ref(name, create_parent=True)

        def publish_owned() -> str:
            descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                Path(temporary).replace(target)
                return str(target)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise

        return self._writer_actor.call(f"publish:{name}", publish_owned)

    def append_json(
        self,
        name: str,
        payload: JsonObject,
        *,
        kind: RunArtifactKind,
    ) -> str:
        target = self._resolve_ref(name, create_parent=True)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=json_default) + "\n"

        def append_owned() -> str:
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return str(target)

        return self._writer_actor.call(f"append:{name}", append_owned)

    def _snapshot_unlocked(
        self,
        artifact_ref: str,
        *,
        kind: RunArtifactKind,
        record_stream: bool,
        error_type: type[RuntimeError],
    ) -> RunArtifactSnapshotReceipt:
        if type(kind) is not RunArtifactKind:
            raise error_type("run artifact snapshot kind is invalid")
        if type(record_stream) is not bool:
            raise error_type("run artifact record_stream flag must be boolean")
        target = self._resolve_ref(artifact_ref, create_parent=False)
        if not target.is_file():
            raise error_type(f"run artifact is missing or not a regular file: {artifact_ref}")
        before = target.stat()
        hasher = hashlib.sha256()
        byte_size = 0
        record_count = 0 if record_stream else None
        try:
            with target.open("rb") as handle:
                if record_stream:
                    for line in handle:
                        hasher.update(line)
                        byte_size += len(line)
                        assert record_count is not None
                        record_count += 1
                else:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        hasher.update(chunk)
                        byte_size += len(chunk)
        except OSError as exc:
            raise error_type(f"run artifact cannot be read: {artifact_ref}") from exc
        after = target.stat()
        before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if before_identity != after_identity or after.st_size != byte_size:
            raise error_type(f"run artifact changed during snapshot: {artifact_ref}")
        content_sha256 = hasher.hexdigest()
        generation = canonical_digest(
            {
                "run_id": self.run_id,
                "artifact_ref": artifact_ref,
                "artifact_kind": kind.value,
                "device": int(after.st_dev),
                "inode": int(after.st_ino),
                "mtime_ns": int(after.st_mtime_ns),
                "ctime_ns": int(after.st_ctime_ns),
                "content_sha256": content_sha256,
                "byte_size": byte_size,
                "record_count": record_count,
            }
        )
        return RunArtifactSnapshotReceipt(
            run_id=self.run_id,
            artifact_ref=artifact_ref,
            artifact_kind=kind,
            generation=generation,
            content_sha256=content_sha256,
            byte_size=byte_size,
            record_count=record_count,
        )

    def _ledger_path(self, generation: str, *, create_parent: bool) -> Path:
        directory = self.root / _FINALIZED_DIR
        if create_parent:
            directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{generation}.json"

    @staticmethod
    def _write_atomic_bytes(target: Path, payload: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def finalize(
        self,
        artifact_ref: str,
        *,
        kind: RunArtifactKind,
        record_stream: bool,
    ) -> RunArtifactSnapshotReceipt:
        def finalize_owned() -> RunArtifactSnapshotReceipt:
            receipt = self._snapshot_unlocked(
                artifact_ref,
                kind=kind,
                record_stream=record_stream,
                error_type=RunArtifactFinalizationError,
            )
            payload = canonical_bytes(receipt, indent=2) + b"\n"
            ledger = self._ledger_path(receipt.generation, create_parent=True)
            if ledger.exists():
                if ledger.read_bytes() != payload:
                    raise RunArtifactFinalizationError("run artifact finalized ledger conflicts with receipt")
            else:
                self._write_atomic_bytes(ledger, payload)
            return receipt

        return self._writer_actor.call(f"finalize:{artifact_ref}", finalize_owned)

    def verify_finalized(self, receipt: RunArtifactSnapshotReceipt) -> RunArtifactSnapshotReceipt:
        if type(receipt) is not RunArtifactSnapshotReceipt:
            raise RunArtifactVerificationError("run artifact verification requires a typed snapshot receipt")
        if receipt.run_id != self.run_id:
            raise RunArtifactVerificationError("run artifact snapshot belongs to a different run")

        def verify_owned() -> RunArtifactSnapshotReceipt:
            ledger = self._ledger_path(receipt.generation, create_parent=False)
            expected = canonical_bytes(receipt, indent=2) + b"\n"
            if not ledger.is_file():
                raise RunArtifactVerificationError("run artifact snapshot was never finalized")
            try:
                recorded = ledger.read_bytes()
            except OSError as exc:
                raise RunArtifactVerificationError("run artifact finalized ledger cannot be read") from exc
            if recorded != expected:
                raise RunArtifactVerificationError("run artifact finalized ledger does not match receipt")
            current = self._snapshot_unlocked(
                receipt.artifact_ref,
                kind=receipt.artifact_kind,
                record_stream=receipt.record_count is not None,
                error_type=RunArtifactVerificationError,
            )
            if current != receipt:
                raise RunArtifactVerificationError("run artifact content or generation drifted after finalization")
            return receipt

        return self._writer_actor.call(f"verify-finalized:{receipt.artifact_ref}", verify_owned)


__all__ = ["DirectoryRunArtifactStore"]
