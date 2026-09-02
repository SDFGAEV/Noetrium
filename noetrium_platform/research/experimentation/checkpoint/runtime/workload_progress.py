from __future__ import annotations

import json
import math

from noetrium_platform.research.experimentation.workload.api import WorkloadCompletionReceipt, WorkloadTaskResult
from noetrium_platform.foundation.kernel.kernel import canonical_bytes


class WorkloadProgressIntegrityError(RuntimeError):
    """A persisted workload-result prefix is malformed or inconsistent."""


_RESULT_FIELDS = frozenset(
    {
        "task_id",
        "family",
        "success",
        "utility",
        "steps",
        "duration_s",
        "lineage_id",
        "failure_reason",
        "memory_queries",
        "planner_actions",
        "decision_cycles",
        "completion_receipt",
        "blocked",
        "failure_scope",
        "diagnostics",
    }
)


def _require_string(row: dict[str, object], field: str) -> str:
    value = row[field]
    if type(value) is not str:
        raise TypeError(f"{field} must be a string")
    return value


def _require_bool(row: dict[str, object], field: str) -> bool:
    value = row[field]
    if type(value) is not bool:
        raise TypeError(f"{field} must be a boolean")
    return value


def _require_int(row: dict[str, object], field: str) -> int:
    value = row[field]
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer")
    return value


def _require_finite_number(row: dict[str, object], field: str) -> float:
    value = row[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field} must be finite")
    return normalized


def _require_object_list(row: dict[str, object], field: str) -> tuple[dict[str, object], ...]:
    value = row[field]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise TypeError(f"{field} must be a list of objects")
    return tuple(dict(item) for item in value)



_COMPLETION_RECEIPT_FIELDS = frozenset({"completion_key", "method_generation", "artifacts"})


def _decode_completion_receipt(value: object) -> WorkloadCompletionReceipt | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _COMPLETION_RECEIPT_FIELDS:
        raise TypeError("completion_receipt fields are not exact")
    completion_key = value["completion_key"]
    method_generation = value["method_generation"]
    artifacts = value["artifacts"]
    if type(completion_key) is not str:
        raise TypeError("completion_receipt completion_key must be a string")
    if method_generation is not None and type(method_generation) is not str:
        raise TypeError("completion_receipt method_generation must be a string or null")
    if not isinstance(artifacts, list) or any(type(item) is not str for item in artifacts):
        raise TypeError("completion_receipt artifacts must be a list of strings")
    return WorkloadCompletionReceipt(completion_key, method_generation, tuple(artifacts))

def _decode_workload_result(row: object) -> WorkloadTaskResult:
    if not isinstance(row, dict) or set(row) != _RESULT_FIELDS:
        raise TypeError("workload progress result fields are not exact")
    diagnostics = row["diagnostics"]
    if not isinstance(diagnostics, dict):
        raise TypeError("diagnostics must be an object")

    return WorkloadTaskResult(
        task_id=_require_string(row, "task_id"), family=_require_string(row, "family"),
        success=_require_bool(row, "success"), utility=_require_finite_number(row, "utility"),
        steps=_require_int(row, "steps"), duration_s=_require_finite_number(row, "duration_s"),
        lineage_id=_require_string(row, "lineage_id"),
        failure_reason=_require_string(row, "failure_reason"),
        memory_queries=_require_int(row, "memory_queries"),
        planner_actions=_require_object_list(row, "planner_actions"),
        decision_cycles=_require_object_list(row, "decision_cycles"),
        completion_receipt=_decode_completion_receipt(row["completion_receipt"]), blocked=_require_bool(row, "blocked"),
        failure_scope=_require_string(row, "failure_scope"), diagnostics=dict(diagnostics),
    )

def _decode_progress_payload(payload: bytes) -> tuple[WorkloadTaskResult, ...]:
    if type(payload) is not bytes:
        raise TypeError("workload progress payload must be bytes")
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != {"results"}:
        raise TypeError("workload progress document fields are not exact")
    rows = document["results"]
    if not isinstance(rows, list):
        raise TypeError("results must be a list")
    return tuple(_decode_workload_result(row) for row in rows)


class WorkloadProgressCheckpointComponent:
    """Checkpoint component for the exact committed result prefix of a task batch."""

    component_id = "workload.progress"
    codec_id = "experimentation.workload.task-results.json"
    schema_version = "1"

    def __init__(self) -> None:
        self._results: list[WorkloadTaskResult] = []
        self._task_ids: set[str] = set()

    @property
    def results(self) -> tuple[WorkloadTaskResult, ...]:
        return tuple(self._results)

    def replace(self, results: tuple[WorkloadTaskResult, ...]) -> None:
        normalized = tuple(results)
        ids = tuple(result.task_id for result in normalized)
        if any(not item.strip() for item in ids) or len(ids) != len(set(ids)):
            raise WorkloadProgressIntegrityError(
                "workload progress requires unique non-empty task ids"
            )
        self._results = list(normalized)
        self._task_ids = set(ids)

    def append(self, result: WorkloadTaskResult) -> None:
        task_id = result.task_id
        if not task_id.strip() or task_id in self._task_ids:
            raise WorkloadProgressIntegrityError(
                "workload progress requires unique non-empty task ids"
            )
        self._results.append(result)
        self._task_ids.add(task_id)

    def capture(self) -> bytes:
        return canonical_bytes({"results": self._results})

    def restore(self, payload: bytes) -> None:
        try:
            self.replace(_decode_progress_payload(payload))
        except WorkloadProgressIntegrityError:
            raise
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise WorkloadProgressIntegrityError(
                "invalid workload progress checkpoint document"
            ) from exc

    @staticmethod
    def _decode_result(row: object) -> WorkloadTaskResult:
        return _decode_workload_result(row)



__all__ = ["WorkloadProgressCheckpointComponent", "WorkloadProgressIntegrityError"]
