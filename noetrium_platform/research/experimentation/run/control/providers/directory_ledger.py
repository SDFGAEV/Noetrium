from __future__ import annotations

import json
from pathlib import Path
import re

from noetrium_platform.research.experimentation.run.api.artifacts import RunArtifactWriteActorPort
from noetrium_platform.foundation.kernel.kernel import canonical_digest
from noetrium_platform.foundation.kernel.kernel.durability import DurableFileWriteError, atomic_replace_bytes
from noetrium_platform.foundation.kernel.kernel.durability.file_lock import InterprocessFileLock

from ..api.contracts import (
    RunControlAction,
    RunControlConflict,
    RunControlEventReceipt,
    RunControlIntegrityError,
    RunControlOperationIntent,
    RunControlPhase,
    RunControlPreparation,
    RunControlPreparedOperation,
    RunControlProjection,
    RunControlRecordKind,
    RunControlStaleGeneration,
)

_SCHEMA_VERSION = "2"
_RECORD_NAME = re.compile(r"^[0-9]{20}\.json$")
_HEX = frozenset("0123456789abcdef")
_RECORD_FIELDS = frozenset({
    "schema_version",
    "record_sequence",
    "record_kind",
    "operation_id",
    "action",
    "run_id",
    "run_identity_digest",
    "run_manifest_digest",
    "base_generation",
    "base_phase",
    "base_latest_checkpoint_id",
    "base_checkpoint_manifest_digest",
    "restore_checkpoint_id",
    "restore_checkpoint_manifest_digest",
    "restore_cycle_identity_digest",
    "terminal_phase",
    "terminal_latest_checkpoint_id",
    "terminal_checkpoint_manifest_digest",
    "previous_record_digest",
    "record_digest",
})


def _sha256(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise RunControlIntegrityError(f"run control ledger {field} is not canonical SHA-256")
    return value


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise RunControlIntegrityError(f"run control ledger {field} must be non-empty")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _canonical_record(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") + b"\n"


def _record_digest(document_without_digest: dict[str, object]) -> str:
    return canonical_digest(document_without_digest)


class DirectoryRunControlLedger:
    """Crash-consistent immutable prepared/terminal run-control authority."""

    def __init__(
        self,
        root: Path | str,
        *,
        run_id: str,
        run_identity_digest: str,
        run_manifest_digest: str,
        writer_actor: RunArtifactWriteActorPort,
    ) -> None:
        if type(run_id) is not str or not run_id.strip():
            raise ValueError("run control ledger run_id must be non-empty")
        self.root = Path(root).expanduser().resolve()
        self.run_id = run_id
        self.run_identity_digest = _sha256(run_identity_digest, "run_identity_digest")
        self.run_manifest_digest = _sha256(run_manifest_digest, "run_manifest_digest")
        self.control_root = self.root / "control"
        self.records_root = self.control_root / "records"
        self.lock_path = self.control_root / "events.lock"
        self._writer_actor = writer_actor

    @staticmethod
    def _require_expected(current: RunControlProjection | None, expected_generation: int) -> None:
        observed = 0 if current is None else current.control_generation
        if expected_generation != observed:
            raise RunControlStaleGeneration(
                f"run control generation is stale: expected={expected_generation} observed={observed}"
            )

    def _record_paths_unlocked(self) -> tuple[Path, ...]:
        if not self.records_root.exists():
            return ()
        if not self.records_root.is_dir() or self.records_root.is_symlink():
            raise RunControlIntegrityError("run control records authority is not a regular directory")
        rows: list[Path] = []
        for path in self.records_root.iterdir():
            if path.name.startswith("."):
                continue
            if not _RECORD_NAME.fullmatch(path.name):
                raise RunControlIntegrityError(f"run control records contain unexpected entry: {path.name}")
            if path.is_symlink() or not path.is_file():
                raise RunControlIntegrityError(f"run control record is not a regular file: {path.name}")
            rows.append(path)
        rows.sort(key=lambda item: item.name)
        for expected, path in enumerate(rows, start=1):
            if path.name != f"{expected:020d}.json":
                raise RunControlIntegrityError("run control record sequence has a gap or duplicate")
        return tuple(rows)

    def _decode_record(self, path: Path) -> dict[str, object]:
        try:
            raw = path.read_bytes()
            document = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunControlIntegrityError(f"run control record cannot be decoded: {path.name}") from exc
        if not raw.endswith(b"\n"):
            raise RunControlIntegrityError(f"run control record is truncated: {path.name}")
        if not isinstance(document, dict):
            raise RunControlIntegrityError("run control record is not a JSON object")
        try:
            canonical = _canonical_record(document)
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise RunControlIntegrityError("run control record is not canonical JSON") from exc
        if canonical != raw:
            raise RunControlIntegrityError("run control record bytes are not canonical JSON")
        if set(document) != _RECORD_FIELDS:
            raise RunControlIntegrityError("run control record fields are not exact")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise RunControlIntegrityError("run control record schema is unsupported")
        return document

    @staticmethod
    def _phase(value: object, field: str, *, optional: bool) -> RunControlPhase | None:
        if value is None and optional:
            return None
        if type(value) is not str:
            raise RunControlIntegrityError(f"run control ledger {field} must be a phase string")
        try:
            return RunControlPhase(value)
        except ValueError as exc:
            raise RunControlIntegrityError(f"run control ledger {field} is unsupported") from exc

    @staticmethod
    def _action(value: object) -> RunControlAction:
        if type(value) is not str:
            raise RunControlIntegrityError("run control ledger action must be a string")
        try:
            action = RunControlAction(value)
        except ValueError as exc:
            raise RunControlIntegrityError("run control ledger action is unsupported") from exc
        if action not in {RunControlAction.RUN, RunControlAction.STOP, RunControlAction.RESUME}:
            raise RunControlIntegrityError("run control prepared action must be effectful lifecycle action")
        return action

    @staticmethod
    def _kind(value: object) -> RunControlRecordKind:
        if type(value) is not str:
            raise RunControlIntegrityError("run control ledger record_kind must be a string")
        try:
            return RunControlRecordKind(value)
        except ValueError as exc:
            raise RunControlIntegrityError("run control ledger record_kind is unsupported") from exc

    def _prepared_from_document(
        self,
        document: dict[str, object],
        *,
        record_digest: str,
    ) -> RunControlPreparedOperation:
        return RunControlPreparedOperation(
            operation_id=_sha256(document["operation_id"], "operation_id"),
            action=self._action(document["action"]),
            base_generation=document["base_generation"],
            base_phase=self._phase(document["base_phase"], "base_phase", optional=True),
            base_latest_checkpoint_id=_optional_text(
                document["base_latest_checkpoint_id"], "base_latest_checkpoint_id"
            ),
            base_checkpoint_manifest_digest=(
                None
                if document["base_checkpoint_manifest_digest"] is None
                else _sha256(document["base_checkpoint_manifest_digest"], "base_checkpoint_manifest_digest")
            ),
            restore_checkpoint_id=_optional_text(document["restore_checkpoint_id"], "restore_checkpoint_id"),
            restore_checkpoint_manifest_digest=(
                None
                if document["restore_checkpoint_manifest_digest"] is None
                else _sha256(document["restore_checkpoint_manifest_digest"], "restore_checkpoint_manifest_digest")
            ),
            restore_cycle_identity_digest=(
                None
                if document["restore_cycle_identity_digest"] is None
                else _sha256(document["restore_cycle_identity_digest"], "restore_cycle_identity_digest")
            ),
            record_sequence=document["record_sequence"],
            record_digest=record_digest,
        )

    @staticmethod
    def _checkpoint_pair(checkpoint_id: object, checkpoint_digest: object, *, prefix: str) -> tuple[str | None, str | None]:
        resolved_id = _optional_text(checkpoint_id, f"{prefix}_checkpoint_id")
        resolved_digest = None if checkpoint_digest is None else _sha256(
            checkpoint_digest, f"{prefix}_checkpoint_manifest_digest"
        )
        if (resolved_id is None) != (resolved_digest is None):
            raise RunControlIntegrityError(f"run control ledger {prefix} checkpoint identity is incomplete")
        return resolved_id, resolved_digest

    def _validate_identity(self, document: dict[str, object], *, sequence: int) -> tuple[str, RunControlRecordKind, RunControlAction]:
        if document["record_sequence"] != sequence or type(document["record_sequence"]) is not int:
            raise RunControlIntegrityError("run control record_sequence is corrupt")
        if _text(document["run_id"], "run_id") != self.run_id:
            raise RunControlIntegrityError("run control ledger belongs to a different run")
        if _sha256(document["run_identity_digest"], "run_identity_digest") != self.run_identity_digest:
            raise RunControlIntegrityError("run control ledger run identity drifted")
        if _sha256(document["run_manifest_digest"], "run_manifest_digest") != self.run_manifest_digest:
            raise RunControlIntegrityError("run control ledger run manifest drifted")
        operation_id = _sha256(document["operation_id"], "operation_id")
        return operation_id, self._kind(document["record_kind"]), self._action(document["action"])

    def _load_unlocked(self) -> RunControlProjection | None:
        paths = self._record_paths_unlocked()
        if not paths:
            return None
        projection: RunControlProjection | None = None
        pending: RunControlPreparedOperation | None = None
        previous_digest: str | None = None
        for sequence, path in enumerate(paths, start=1):
            document = self._decode_record(path)
            operation_id, kind, action = self._validate_identity(document, sequence=sequence)
            previous = document["previous_record_digest"]
            if previous is not None:
                previous = _sha256(previous, "previous_record_digest")
            if previous != previous_digest:
                raise RunControlIntegrityError("run control record hash chain is broken")
            observed_digest = _sha256(document["record_digest"], "record_digest")
            digest_input = dict(document)
            del digest_input["record_digest"]
            if _record_digest(digest_input) != observed_digest:
                raise RunControlIntegrityError("run control record digest mismatch")
            base_generation = document["base_generation"]
            if type(base_generation) is not int or base_generation < 0:
                raise RunControlIntegrityError("run control base_generation is invalid")
            base_phase = self._phase(document["base_phase"], "base_phase", optional=True)
            base_checkpoint_id, base_checkpoint_digest = self._checkpoint_pair(
                document["base_latest_checkpoint_id"],
                document["base_checkpoint_manifest_digest"],
                prefix="base",
            )
            restore_checkpoint_id, restore_checkpoint_digest = self._checkpoint_pair(
                document["restore_checkpoint_id"],
                document["restore_checkpoint_manifest_digest"],
                prefix="restore",
            )
            restore_cycle_digest = document["restore_cycle_identity_digest"]
            if restore_cycle_digest is not None:
                restore_cycle_digest = _sha256(restore_cycle_digest, "restore_cycle_identity_digest")
            if action is RunControlAction.RESUME:
                if restore_checkpoint_id is None or restore_cycle_digest is None:
                    raise RunControlIntegrityError("run control resume record lacks exact restore identity")
            elif restore_checkpoint_id is not None or restore_checkpoint_digest is not None or restore_cycle_digest is not None:
                raise RunControlIntegrityError("non-resume run control record carries restore identity")

            expected_generation = 0 if projection is None else projection.control_generation
            expected_phase = None if projection is None else projection.phase
            expected_checkpoint_id = None if projection is None else projection.latest_checkpoint_id
            expected_checkpoint_digest = None if projection is None else projection.checkpoint_manifest_digest
            if kind is RunControlRecordKind.PREPARED:
                if pending is not None:
                    raise RunControlIntegrityError("run control ledger has overlapping prepared operations")
                if base_generation != expected_generation or base_phase is not expected_phase:
                    raise RunControlIntegrityError("run control prepared base state does not match prior terminal authority")
                if (base_checkpoint_id, base_checkpoint_digest) != (
                    expected_checkpoint_id,
                    expected_checkpoint_digest,
                ):
                    raise RunControlIntegrityError("run control prepared base checkpoint drifted")
                if document["terminal_phase"] is not None or document["terminal_latest_checkpoint_id"] is not None or document["terminal_checkpoint_manifest_digest"] is not None:
                    raise RunControlIntegrityError("run control prepared record carries terminal state")
                pending = self._prepared_from_document(document, record_digest=observed_digest)
                projection = RunControlProjection(
                    run_id=self.run_id,
                    run_identity_digest=self.run_identity_digest,
                    run_manifest_digest=self.run_manifest_digest,
                    phase=RunControlPhase.RECOVERY_REQUIRED,
                    control_generation=base_generation,
                    latest_checkpoint_id=base_checkpoint_id,
                    checkpoint_manifest_digest=base_checkpoint_digest,
                    event_receipt=RunControlEventReceipt(
                        run_id=self.run_id,
                        record_sequence=sequence,
                        record_kind=kind,
                        control_generation=base_generation,
                        action=action,
                        phase=RunControlPhase.RECOVERY_REQUIRED,
                        operation_id=operation_id,
                        event_digest=observed_digest,
                    ),
                    pending_operation=pending,
                )
            else:
                if pending is None or pending.operation_id != operation_id or pending.action is not action:
                    raise RunControlIntegrityError("run control terminal record does not resolve the pending operation")
                if base_generation != pending.base_generation or base_phase is not pending.base_phase:
                    raise RunControlIntegrityError("run control terminal base identity drifted")
                if (base_checkpoint_id, base_checkpoint_digest) != (
                    pending.base_latest_checkpoint_id,
                    pending.base_checkpoint_manifest_digest,
                ):
                    raise RunControlIntegrityError("run control terminal base checkpoint drifted")
                if (restore_checkpoint_id, restore_checkpoint_digest, restore_cycle_digest) != (
                    pending.restore_checkpoint_id,
                    pending.restore_checkpoint_manifest_digest,
                    pending.restore_cycle_identity_digest,
                ):
                    raise RunControlIntegrityError("run control terminal restore identity drifted")
                terminal_phase = self._phase(document["terminal_phase"], "terminal_phase", optional=False)
                assert terminal_phase is not None
                if terminal_phase is RunControlPhase.RECOVERY_REQUIRED:
                    raise RunControlIntegrityError("uncertain run control operation cannot be terminalized")
                terminal_checkpoint_id, terminal_checkpoint_digest = self._checkpoint_pair(
                    document["terminal_latest_checkpoint_id"],
                    document["terminal_checkpoint_manifest_digest"],
                    prefix="terminal",
                )
                generation = pending.base_generation + 1
                projection = RunControlProjection(
                    run_id=self.run_id,
                    run_identity_digest=self.run_identity_digest,
                    run_manifest_digest=self.run_manifest_digest,
                    phase=terminal_phase,
                    control_generation=generation,
                    latest_checkpoint_id=terminal_checkpoint_id,
                    checkpoint_manifest_digest=terminal_checkpoint_digest,
                    event_receipt=RunControlEventReceipt(
                        run_id=self.run_id,
                        record_sequence=sequence,
                        record_kind=kind,
                        control_generation=generation,
                        action=action,
                        phase=terminal_phase,
                        operation_id=operation_id,
                        event_digest=observed_digest,
                    ),
                    pending_operation=None,
                )
                pending = None
            previous_digest = observed_digest
        return projection

    def _publish_unlocked(self, sequence: int, document: dict[str, object]) -> bytes:
        digest_input = dict(document)
        digest_input["record_digest"] = None
        # record_digest is defined over all fields except itself.
        del digest_input["record_digest"]
        document["record_digest"] = _record_digest(digest_input)
        payload = _canonical_record(document)
        target = self.records_root / f"{sequence:020d}.json"
        if target.exists():
            try:
                if target.is_file() and not target.is_symlink() and target.read_bytes() == payload:
                    return payload
            except OSError:
                pass
            raise RunControlIntegrityError("run control immutable record target already exists with different content")
        try:
            atomic_replace_bytes(target, payload)
        except DurableFileWriteError as publication_error:
            # If replace happened but durability flush reported failure, re-publish the exact
            # immutable payload. This is safe because no lifecycle effect is issued until
            # PREPARED publication returns successfully, and TERMINAL is deterministic.
            try:
                if target.is_file() and not target.is_symlink() and target.read_bytes() == payload:
                    atomic_replace_bytes(target, payload)
                    return payload
            except (OSError, DurableFileWriteError) as exc:
                raise RunControlIntegrityError("run control immutable record publication is uncertain") from exc
            raise RunControlIntegrityError(
                "run control immutable record publication failed before durable authority"
            ) from publication_error
        return payload

    def _prepared_document(
        self,
        *,
        sequence: int,
        intent: RunControlOperationIntent,
        current: RunControlProjection | None,
        previous_digest: str | None,
    ) -> dict[str, object]:
        base_phase = None if current is None else current.phase.value
        return {
            "schema_version": _SCHEMA_VERSION,
            "record_sequence": sequence,
            "record_kind": RunControlRecordKind.PREPARED.value,
            "operation_id": intent.operation_id,
            "action": intent.action.value,
            "run_id": self.run_id,
            "run_identity_digest": self.run_identity_digest,
            "run_manifest_digest": self.run_manifest_digest,
            "base_generation": intent.base_generation,
            "base_phase": base_phase,
            "base_latest_checkpoint_id": None if current is None else current.latest_checkpoint_id,
            "base_checkpoint_manifest_digest": None if current is None else current.checkpoint_manifest_digest,
            "restore_checkpoint_id": intent.restore_checkpoint_id,
            "restore_checkpoint_manifest_digest": intent.restore_checkpoint_manifest_digest,
            "restore_cycle_identity_digest": intent.restore_cycle_identity_digest,
            "terminal_phase": None,
            "terminal_latest_checkpoint_id": None,
            "terminal_checkpoint_manifest_digest": None,
            "previous_record_digest": previous_digest,
            "record_digest": None,
        }

    def read(self, *, expected_generation: int | None = None) -> RunControlProjection | None:
        def owned() -> RunControlProjection | None:
            with InterprocessFileLock(self.lock_path):
                current = self._load_unlocked()
                if expected_generation is not None:
                    self._require_expected(current, expected_generation)
                return current
        return self._writer_actor.call("run-control:read", owned)

    def prepare(self, intent: RunControlOperationIntent) -> RunControlPreparation:
        if type(intent) is not RunControlOperationIntent:
            raise ValueError("run control ledger prepare requires RunControlOperationIntent")

        def owned() -> RunControlPreparation:
            with InterprocessFileLock(self.lock_path):
                current = self._load_unlocked()
                if current is not None and current.pending_operation is not None:
                    pending = current.pending_operation
                    exact = (
                        pending.operation_id == intent.operation_id
                        and pending.action is intent.action
                        and pending.base_generation == intent.base_generation
                        and pending.restore_checkpoint_id == intent.restore_checkpoint_id
                        and pending.restore_checkpoint_manifest_digest == intent.restore_checkpoint_manifest_digest
                        and pending.restore_cycle_identity_digest == intent.restore_cycle_identity_digest
                    )
                    if exact:
                        return RunControlPreparation(current, pending, False)
                    raise RunControlConflict("run control has an unresolved prepared operation")
                self._require_expected(current, intent.base_generation)
                if intent.action is RunControlAction.RUN:
                    if current is not None and current.phase is not RunControlPhase.FAILED:
                        raise RunControlConflict(
                            f"run control run cannot replace existing phase {current.phase.value}; use resume"
                        )
                elif current is None:
                    raise RunControlIntegrityError("run control stop/resume requires existing state")
                elif intent.action is RunControlAction.STOP and current.phase not in {
                    RunControlPhase.RUNNING,
                    RunControlPhase.FAILED,
                }:
                    raise RunControlConflict(f"run control stop is invalid from phase {current.phase.value}")
                elif intent.action is RunControlAction.RESUME and current.phase not in {
                    RunControlPhase.STOPPED,
                    RunControlPhase.FAILED,
                }:
                    raise RunControlConflict(f"run control resume is invalid from phase {current.phase.value}")
                paths = self._record_paths_unlocked()
                sequence = len(paths) + 1
                previous_digest = None if not paths else _sha256(
                    self._decode_record(paths[-1])["record_digest"], "record_digest"
                )
                document = self._prepared_document(
                    sequence=sequence,
                    intent=intent,
                    current=current,
                    previous_digest=previous_digest,
                )
                self._publish_unlocked(sequence, document)
                projected = self._load_unlocked()
                if projected is None or projected.pending_operation is None:
                    raise RunControlIntegrityError("run control prepared publication did not reconstruct")
                return RunControlPreparation(projected, projected.pending_operation, True)

        return self._writer_actor.call(f"run-control:prepare:{intent.operation_id}", owned)

    def commit(
        self,
        operation_id: str,
        *,
        phase: RunControlPhase,
        latest_checkpoint_id: str | None,
        checkpoint_manifest_digest: str | None,
    ) -> RunControlProjection:
        _sha256(operation_id, "operation_id")
        if type(phase) is not RunControlPhase or phase is RunControlPhase.RECOVERY_REQUIRED:
            raise ValueError("run control terminal commit requires authoritative non-recovery phase")

        def owned() -> RunControlProjection:
            with InterprocessFileLock(self.lock_path):
                current = self._load_unlocked()
                if current is None or current.pending_operation is None:
                    raise RunControlConflict("run control has no prepared operation to commit")
                pending = current.pending_operation
                if pending.operation_id != operation_id:
                    raise RunControlConflict("run control terminal operation id does not match pending authority")
                terminal_checkpoint_id = _optional_text(latest_checkpoint_id, "terminal_latest_checkpoint_id")
                terminal_checkpoint_digest = (
                    None
                    if checkpoint_manifest_digest is None
                    else _sha256(checkpoint_manifest_digest, "terminal_checkpoint_manifest_digest")
                )
                if (terminal_checkpoint_id is None) != (terminal_checkpoint_digest is None):
                    raise RunControlIntegrityError("run control terminal checkpoint identity is incomplete")
                sequence = current.event_receipt.record_sequence + 1
                document = {
                    "schema_version": _SCHEMA_VERSION,
                    "record_sequence": sequence,
                    "record_kind": RunControlRecordKind.TERMINAL.value,
                    "operation_id": pending.operation_id,
                    "action": pending.action.value,
                    "run_id": self.run_id,
                    "run_identity_digest": self.run_identity_digest,
                    "run_manifest_digest": self.run_manifest_digest,
                    "base_generation": pending.base_generation,
                    "base_phase": None if pending.base_phase is None else pending.base_phase.value,
                    "base_latest_checkpoint_id": pending.base_latest_checkpoint_id,
                    "base_checkpoint_manifest_digest": pending.base_checkpoint_manifest_digest,
                    "restore_checkpoint_id": pending.restore_checkpoint_id,
                    "restore_checkpoint_manifest_digest": pending.restore_checkpoint_manifest_digest,
                    "restore_cycle_identity_digest": pending.restore_cycle_identity_digest,
                    "terminal_phase": phase.value,
                    "terminal_latest_checkpoint_id": terminal_checkpoint_id,
                    "terminal_checkpoint_manifest_digest": terminal_checkpoint_digest,
                    "previous_record_digest": pending.record_digest,
                    "record_digest": None,
                }
                self._publish_unlocked(sequence, document)
                projection = self._load_unlocked()
                if projection is None or projection.pending_operation is not None:
                    raise RunControlIntegrityError("run control terminal publication did not reconstruct")
                return projection

        return self._writer_actor.call(f"run-control:commit:{operation_id}", owned)


__all__ = ["DirectoryRunControlLedger"]
