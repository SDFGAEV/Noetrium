from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from research_platform.platform.kernel.retry import retry_until_deadline
from research_platform.execution.operation.api import EffectId, OperationId
from research_platform.execution.workflow.api.progress import (
    WorkflowOperationBinding,
    WorkflowProgress,
    WorkflowProgressConflict,
    WorkflowProgressCorruption,
    WorkflowRunId,
)



class SQLiteWorkflowProgressStore:
    """SQLite WAL authority for exact workflow step/operation ancestry."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def durability(self) -> str:
        return "sqlite-wal"

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=30.0, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self) -> None:
        retry_until_deadline(
            self._initialize_once,
            should_retry=lambda exc: isinstance(exc, sqlite3.OperationalError)
            and "locked" in str(exc).lower(),
            timeout_seconds=30.0,
        )

    def _initialize_once(self) -> None:
        with closing(self._connect()) as db, db:
            if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                db.execute("PRAGMA journal_mode=WAL").fetchone()
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_progress (
                workflow_run_id TEXT PRIMARY KEY,
                graph_digest TEXT NOT NULL,
                version INTEGER NOT NULL,
                completed_json TEXT NOT NULL,
                running_json TEXT NOT NULL,
                uncertain_json TEXT NOT NULL,
                failed_json TEXT,
                cancellation_requested INTEGER NOT NULL,
                cancellation_reason TEXT
            )""")
            columns = tuple(row[1] for row in db.execute("PRAGMA table_info(workflow_progress)"))
            expected = (
                "workflow_run_id", "graph_digest", "version", "completed_json", "running_json",
                "uncertain_json", "failed_json", "cancellation_requested", "cancellation_reason",
            )
            if columns != expected:
                raise WorkflowProgressCorruption(
                    "workflow progress schema does not match current durable contract"
                )
        return

    @staticmethod
    def _json_list(value: object, *, field: str) -> list[object]:
        if not isinstance(value, str):
            raise WorkflowProgressCorruption(f"workflow {field} must be JSON text")
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WorkflowProgressCorruption(f"workflow {field} contains invalid JSON") from exc
        if not isinstance(decoded, list):
            raise WorkflowProgressCorruption(f"workflow {field} must decode to a list")
        return decoded

    @classmethod
    def _bindings(cls, value: object, *, field: str) -> tuple[WorkflowOperationBinding, ...]:
        rows = cls._json_list(value, field=field)
        bindings: list[WorkflowOperationBinding] = []
        for row in rows:
            if not isinstance(row, list) or len(row) != 5:
                raise WorkflowProgressCorruption(
                    f"workflow {field} binding must be [step_id, operation_id, effect_id, request_id, request_digest]"
                )
            if not isinstance(row[0], str) or not isinstance(row[1], str):
                raise WorkflowProgressCorruption(f"workflow {field} step/operation identity must be text")
            effect_values = row[2:5]
            if not (all(value is None for value in effect_values) or all(isinstance(value, str) for value in effect_values)):
                raise WorkflowProgressCorruption(f"workflow {field} effect identity must be all-text or all-null")
            bindings.append(WorkflowOperationBinding(
                row[0], OperationId(row[1]),
                None if row[2] is None else EffectId(row[2]),
                row[3], row[4],
            ))
        return tuple(bindings)

    @classmethod
    def _failed_binding(cls, value: object) -> WorkflowOperationBinding | None:
        if value is None:
            return None
        rows = cls._json_list(value, field="failed_json")
        if len(rows) != 1:
            raise WorkflowProgressCorruption("workflow failed_json must contain exactly one binding")
        encoded = json.dumps(rows, separators=(",", ":"))
        return cls._bindings(encoded, field="failed_json")[0]

    @staticmethod
    def _binding_json(bindings: tuple[WorkflowOperationBinding, ...]) -> str:
        return json.dumps(
            [[item.step_id, item.operation_id.value,
              None if item.effect_id is None else item.effect_id.value,
              item.effect_request_id, item.effect_request_digest] for item in bindings],
            separators=(",", ":"),
        )

    @classmethod
    def _decode(cls, row: tuple[object, ...]) -> WorkflowProgress:
        if not isinstance(row, tuple) or len(row) != 9:
            raise WorkflowProgressCorruption("workflow progress row shape is invalid")
        if not isinstance(row[0], str) or not isinstance(row[1], str):
            raise WorkflowProgressCorruption("workflow identity/digest columns must be text")
        if not isinstance(row[2], int) or isinstance(row[2], bool):
            raise WorkflowProgressCorruption("workflow progress version must be integer")
        if not isinstance(row[7], int) or row[7] not in (0, 1):
            raise WorkflowProgressCorruption("workflow cancellation flag must be 0 or 1")
        if row[8] is not None and not isinstance(row[8], str):
            raise WorkflowProgressCorruption("workflow cancellation_reason must be text or null")
        try:
            return WorkflowProgress(
                WorkflowRunId(row[0]),
                row[1],
                row[2],
                cls._bindings(row[3], field="completed_json"),
                cls._bindings(row[4], field="running_json"),
                cls._bindings(row[5], field="uncertain_json"),
                cls._failed_binding(row[6]),
                bool(row[7]),
                row[8],
            )
        except (TypeError, ValueError) as exc:
            raise WorkflowProgressCorruption("workflow progress row violates typed contract") from exc

    def _values(self, progress: WorkflowProgress) -> tuple[object, ...]:
        return (
            progress.workflow_run_id.value,
            progress.graph_digest,
            progress.version,
            self._binding_json(progress.completed),
            self._binding_json(progress.running),
            self._binding_json(progress.uncertain),
            None if progress.failed is None else self._binding_json((progress.failed,)),
            int(progress.cancellation_requested),
            progress.cancellation_reason,
        )

    @staticmethod
    def _validate_initial(progress: WorkflowProgress) -> None:
        if (
            progress.version != 0
            or progress.completed
            or progress.running
            or progress.uncertain
            or progress.failed is not None
            or progress.cancellation_requested
        ):
            raise WorkflowProgressConflict(
                f"new workflow progress must start empty at version 0: {progress.workflow_run_id.value}"
            )

    def create(self, progress: WorkflowProgress) -> WorkflowProgress:
        self._validate_initial(progress)
        try:
            with closing(self._connect()) as db, db:
                db.execute("INSERT INTO workflow_progress VALUES (?,?,?,?,?,?,?,?,?)", self._values(progress))
        except sqlite3.IntegrityError as exc:
            raise WorkflowProgressConflict(f"workflow already exists: {progress.workflow_run_id.value}") from exc
        return progress

    def load(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress | None:
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT workflow_run_id,graph_digest,version,completed_json,running_json,uncertain_json,"
                "failed_json,cancellation_requested,cancellation_reason FROM workflow_progress WHERE workflow_run_id=?",
                (workflow_run_id.value,),
            ).fetchone()
        return None if row is None else self._decode(row)

    @staticmethod
    def _validate_successor(
        current: WorkflowProgress, expected_version: int, progress: WorkflowProgress
    ) -> None:
        if current.version != expected_version or progress.version != expected_version + 1:
            raise WorkflowProgressConflict(f"workflow version conflict: {progress.workflow_run_id.value}")
        if current.workflow_run_id != progress.workflow_run_id or current.graph_digest != progress.graph_digest:
            raise WorkflowProgressConflict(
                f"workflow immutable identity changed during CAS: {progress.workflow_run_id.value}"
            )
        if current.cancellation_requested and (
            not progress.cancellation_requested or progress.cancellation_reason != current.cancellation_reason
        ):
            raise WorkflowProgressConflict(
                f"workflow cancellation evidence regressed during CAS: {progress.workflow_run_id.value}"
            )
        if current.failed is not None and progress.failed != current.failed:
            raise WorkflowProgressConflict(
                f"workflow first failure changed during CAS: {progress.workflow_run_id.value}"
            )

        candidates: list[WorkflowProgress] = []
        next_version = current.version + 1
        if not current.cancellation_requested and progress.cancellation_requested:
            candidates.append(replace(
                current, version=next_version, cancellation_requested=True,
                cancellation_reason=progress.cancellation_reason,
            ))
        if not current.cancellation_requested and current.failed is None:
            for binding in progress.running:
                if binding not in current.running:
                    candidates.append(replace(
                        current, version=next_version, running=current.running + (binding,),
                    ))
        for binding in current.running:
            candidates.append(replace(
                current, version=next_version,
                running=tuple(item for item in current.running if item != binding),
                completed=tuple(sorted((*current.completed, binding), key=lambda item: item.step_id)),
            ))
        if current.failed is None:
            for binding in (*current.running, *current.uncertain):
                candidates.append(replace(
                    current, version=next_version, failed=binding,
                    running=tuple(item for item in current.running if item != binding),
                    uncertain=tuple(item for item in current.uncertain if item != binding),
                ))
        if current.running:
            candidates.append(replace(
                current, version=next_version,
                uncertain=tuple(sorted((*current.uncertain, *current.running), key=lambda item: item.step_id)),
                running=(),
            ))
        for binding in current.uncertain:
            remaining = tuple(item for item in current.uncertain if item != binding)
            candidates.append(replace(
                current, version=next_version, uncertain=remaining,
                completed=tuple(sorted((*current.completed, binding), key=lambda item: item.step_id)),
            ))
            candidates.append(replace(current, version=next_version, uncertain=remaining))
            if current.failed is None:
                candidates.append(replace(
                    current, version=next_version, uncertain=remaining, failed=binding,
                ))
        if progress not in candidates:
            raise WorkflowProgressConflict(
                f"workflow CAS successor violates progress authority: {progress.workflow_run_id.value}"
            )

    def compare_and_swap(self, expected_version: int, progress: WorkflowProgress) -> WorkflowProgress:
        values = self._values(progress)
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT workflow_run_id,graph_digest,version,completed_json,running_json,uncertain_json,"
                "failed_json,cancellation_requested,cancellation_reason FROM workflow_progress WHERE workflow_run_id=?",
                (progress.workflow_run_id.value,),
            ).fetchone()
            if row is None:
                raise WorkflowProgressConflict(f"workflow version conflict: {progress.workflow_run_id.value}")
            current = self._decode(row)
            self._validate_successor(current, expected_version, progress)
            cursor = db.execute(
                """UPDATE workflow_progress SET version=?,completed_json=?,running_json=?,
                uncertain_json=?,failed_json=?,cancellation_requested=?,cancellation_reason=?
                WHERE workflow_run_id=? AND version=? AND graph_digest=?""",
                (
                    values[2], values[3], values[4], values[5], values[6], values[7], values[8],
                    values[0], expected_version, values[1],
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowProgressConflict(f"workflow version conflict: {progress.workflow_run_id.value}")
        return progress


__all__ = ["SQLiteWorkflowProgressStore"]
