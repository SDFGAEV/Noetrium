from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3

from ..api.json_contract import decode_string_map
from ..api.errors import TelemetryMetricCorruptionError


@dataclass(frozen=True, slots=True)
class MetricSummary:
    metric: str
    count: int
    minimum: float
    maximum: float
    mean: float
    p50: float
    p95: float
    p99: float


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise TelemetryMetricCorruptionError(f"{label} must be a string")
    return value


def _optional_string(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label=label)


def _finite_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TelemetryMetricCorruptionError(f"{label} must be numeric")
    decoded = float(value)
    if not math.isfinite(decoded):
        raise TelemetryMetricCorruptionError(f"{label} must be finite")
    return decoded


def _string_map(value: object, *, label: str) -> dict[str, str]:
    return decode_string_map(_string(value, label=label), label=label)


class SQLiteTelemetryReader:
    """Strictly read-only SQLite metric query and summary backend."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        uri = f"file:{self.path.resolve().as_posix()}?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=30)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def query(
        self,
        *,
        run_id: str,
        metric: str | None = None,
        decision_cycle_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[dict[str, int | float | str | None | dict[str, str]], ...]:
        if limit <= 0:
            return ()
        clauses = ["run_id=?"]
        args: list[object] = [run_id]
        if metric is not None:
            clauses.append("metric=?")
            args.append(metric)
        if decision_cycle_id is not None:
            clauses.append("decision_cycle_id=?")
            args.append(decision_cycle_id)
        args.append(limit)
        sql = (
            "SELECT sequence,metric,value,timestamp,run_id,task_id,decision_cycle_id,trace_id,span_id,"
            "operation_id,component_id,dimensions_json FROM metric_observations WHERE "
            f"{' AND '.join(clauses)} ORDER BY sequence LIMIT ?"
        )
        with closing(self._connect()) as db:
            rows = db.execute(sql, args).fetchall()
        result: list[dict[str, int | float | str | None | dict[str, str]]] = []
        for row in rows:
            if len(row) != 12:
                raise TelemetryMetricCorruptionError("telemetry query row has an invalid field count")
            sequence = row[0]
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
                raise TelemetryMetricCorruptionError("telemetry sequence must be a positive integer")
            result.append({
                "sequence": sequence,
                "metric": _string(row[1], label="metric"),
                "value": _finite_number(row[2], label="metric value"),
                "timestamp": _finite_number(row[3], label="metric timestamp"),
                "run_id": _string(row[4], label="run_id"),
                "task_id": _optional_string(row[5], label="task_id"),
                "decision_cycle_id": _optional_string(row[6], label="decision_cycle_id"),
                "trace_id": _string(row[7], label="trace_id"),
                "span_id": _string(row[8], label="span_id"),
                "operation_id": _optional_string(row[9], label="operation_id"),
                "component_id": _optional_string(row[10], label="component_id"),
                "dimensions": _string_map(row[11], label="dimensions_json"),
            })
        return tuple(result)

    @staticmethod
    def _percentile_positions(count: int, q: float) -> tuple[int, int, float]:
        position = (count - 1) * q
        low = int(math.floor(position))
        high = int(math.ceil(position))
        return low, high, position - low

    def summarize(self, *, run_id: str, metric: str) -> MetricSummary:
        """Summarize from one read snapshot with bounded Python memory."""
        index = "idx_metric_run_name_value"
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            corrupt = db.execute(
                f"SELECT value FROM metric_observations INDEXED BY {index} "
                "WHERE run_id=? AND metric=? AND ("
                "typeof(value) NOT IN ('integer','real') OR value != value "
                "OR value >= 1e999 OR value <= -1e999) LIMIT 1",
                (run_id, metric),
            ).fetchone()
            if corrupt is not None:
                raise TelemetryMetricCorruptionError("telemetry summary contains a corrupt metric value")

            aggregate = db.execute(
                f"SELECT COUNT(*),MIN(value),MAX(value),SUM(value) "
                f"FROM metric_observations INDEXED BY {index} "
                "WHERE run_id=? AND metric=?",
                (run_id, metric),
            ).fetchone()
            if aggregate is None or isinstance(aggregate[0], bool) or not isinstance(aggregate[0], int):
                raise TelemetryMetricCorruptionError("telemetry summary aggregate is invalid")
            count = aggregate[0]
            if count == 0:
                raise KeyError(f"no observations for run={run_id!r} metric={metric!r}")
            minimum = _finite_number(aggregate[1], label="metric minimum")
            maximum = _finite_number(aggregate[2], label="metric maximum")
            total = _finite_number(aggregate[3], label="metric sum")

            p50_low, p50_high, p50_fraction = self._percentile_positions(count, 0.50)
            p95_low, p95_high, p95_fraction = self._percentile_positions(count, 0.95)
            p99_low, p99_high, p99_fraction = self._percentile_positions(count, 0.99)
            percentile_row = db.execute(
                f"WITH ordered AS ("
                f"SELECT value, ROW_NUMBER() OVER (ORDER BY value) - 1 AS position "
                f"FROM metric_observations INDEXED BY {index} "
                "WHERE run_id=? AND metric=?"
                ") SELECT "
                "MAX(CASE WHEN position=? THEN value END),"
                "MAX(CASE WHEN position=? THEN value END),"
                "MAX(CASE WHEN position=? THEN value END),"
                "MAX(CASE WHEN position=? THEN value END),"
                "MAX(CASE WHEN position=? THEN value END),"
                "MAX(CASE WHEN position=? THEN value END) FROM ordered",
                (
                    run_id, metric,
                    p50_low, p50_high, p95_low, p95_high, p99_low, p99_high,
                ),
            ).fetchone()
            if percentile_row is None or len(percentile_row) != 6:
                raise TelemetryMetricCorruptionError("telemetry percentile lookup is incomplete")
            p50_low_value = _finite_number(percentile_row[0], label="metric percentile value")
            p50_high_value = _finite_number(percentile_row[1], label="metric percentile value")
            p95_low_value = _finite_number(percentile_row[2], label="metric percentile value")
            p95_high_value = _finite_number(percentile_row[3], label="metric percentile value")
            p99_low_value = _finite_number(percentile_row[4], label="metric percentile value")
            p99_high_value = _finite_number(percentile_row[5], label="metric percentile value")

        return MetricSummary(
            metric=metric,
            count=count,
            minimum=minimum,
            maximum=maximum,
            mean=total / count,
            p50=p50_low_value + (p50_high_value - p50_low_value) * p50_fraction,
            p95=p95_low_value + (p95_high_value - p95_low_value) * p95_fraction,
            p99=p99_low_value + (p99_high_value - p99_low_value) * p99_fraction,
        )


__all__ = ["MetricSummary", "SQLiteTelemetryReader"]
