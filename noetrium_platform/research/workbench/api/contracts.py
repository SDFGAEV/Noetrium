"""Backend-neutral research data, statistics, and publication contracts."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from noetrium_platform.foundation.kernel.kernel import JsonValue, canonical_digest, freeze_json

_HEX = frozenset("0123456789abcdef")


def _text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _sha(value: object, field_name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, field_name)
    if len(value) != 64 or any(char not in _HEX for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class DataColumn:
    name: str
    data_type: str = "unknown"
    nullable: bool = True

    def __post_init__(self) -> None:
        _text(self.name, "data column name")
        _text(self.data_type, "data column data_type")
        if type(self.nullable) is not bool:
            raise TypeError("data column nullable must be boolean")


@dataclass(frozen=True, slots=True)
class DataTable:
    """Immutable tabular value object; physical files stay behind reader ports."""

    table_id: str
    columns: tuple[DataColumn, ...]
    rows: tuple[tuple[JsonValue, ...], ...]
    source_digest: str | None = None
    lineage_digests: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    table_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.table_id, "data table table_id")
        if type(self.columns) is not tuple or not self.columns:
            raise TypeError("data table columns must be a non-empty tuple")
        if any(type(column) is not DataColumn for column in self.columns):
            raise TypeError("data table columns must contain DataColumn")
        names = tuple(column.name for column in self.columns)
        if len(names) != len(set(names)):
            raise ValueError("data table column names must be unique")
        if type(self.rows) is not tuple:
            raise TypeError("data table rows must be a tuple")
        width = len(self.columns)
        frozen_rows = []
        for row in self.rows:
            if type(row) is not tuple or len(row) != width:
                raise ValueError("data table rows must match schema width")
            frozen_rows.append(tuple(freeze_json(value) for value in row))
        object.__setattr__(self, "rows", tuple(frozen_rows))
        _sha(self.source_digest, "data table source_digest", optional=True)
        if type(self.lineage_digests) is not tuple:
            raise TypeError("data table lineage_digests must be a tuple")
        for digest in self.lineage_digests:
            _sha(digest, "data table lineage digest")
        if len(set(self.lineage_digests)) != len(self.lineage_digests):
            raise ValueError("data table lineage_digests must be unique")
        if type(self.metadata) is not tuple:
            raise TypeError("data table metadata must be a tuple")
        if any(type(item) is not tuple or len(item) != 2 or not item[0].strip() for item in self.metadata):
            raise ValueError("data table metadata must contain key/value pairs")
        if len({item[0] for item in self.metadata}) != len(self.metadata):
            raise ValueError("data table metadata keys must be unique")
        object.__setattr__(self, "table_digest", canonical_digest({
            "table_id": self.table_id,
            "columns": tuple((c.name, c.data_type, c.nullable) for c in self.columns),
            "rows": self.rows,
            "source_digest": self.source_digest,
            "lineage": self.lineage_digests,
            "metadata": self.metadata,
        }))

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def column_index(self, name: str) -> int:
        try:
            return self.column_names.index(name)
        except ValueError as exc:
            raise KeyError(f"data table has no column {name!r}") from exc

    def values(self, name: str) -> tuple[JsonValue, ...]:
        index = self.column_index(name)
        return tuple(row[index] for row in self.rows)


class MissingValuePolicy(StrEnum):
    REJECT = "reject"
    SKIP = "skip"


class TableReaderPort(Protocol):
    def read(self, source: str, *, table_id: str) -> DataTable: ...


class TableTransformPort(Protocol):
    def apply(self, table: DataTable) -> DataTable: ...


class TableAnalysisPort(Protocol):
    def summarize(self, table: DataTable, value_column: str, *, group_by: tuple[str, ...] = ()) -> tuple["MetricSummary", ...]: ...


@dataclass(frozen=True, slots=True)
class MetricSummary:
    metric: str
    group: tuple[tuple[str, JsonValue], ...]
    count: int
    mean: float
    variance: float
    standard_deviation: float
    standard_error: float
    minimum: float
    median: float
    maximum: float
    confidence95_low: float
    confidence95_high: float

    def __post_init__(self) -> None:
        _text(self.metric, "metric summary metric")
        if type(self.count) is not int or self.count < 1:
            raise ValueError("metric summary count must be positive")
        values = (self.mean, self.variance, self.standard_deviation, self.standard_error,
                  self.minimum, self.median, self.maximum, self.confidence95_low, self.confidence95_high)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            raise ValueError("metric summary values must be finite numeric")
        if self.variance < 0 or self.standard_deviation < 0 or self.standard_error < 0:
            raise ValueError("metric summary uncertainty values cannot be negative")
        if self.minimum > self.maximum or self.confidence95_low > self.confidence95_high:
            raise ValueError("metric summary bounds are invalid")


@dataclass(frozen=True, slots=True)
class GroupComparison:
    metric: str
    group_column: str
    baseline: JsonValue
    candidate: JsonValue
    baseline_count: int
    candidate_count: int
    difference: float
    relative_difference: float | None
    standardized_effect: float | None
    confidence95_low: float
    confidence95_high: float

    def __post_init__(self) -> None:
        _text(self.metric, "group comparison metric")
        _text(self.group_column, "group comparison group_column")
        if self.baseline == self.candidate:
            raise ValueError("comparison groups must differ")
        if type(self.baseline_count) is not int or self.baseline_count < 1:
            raise ValueError("baseline_count must be positive")
        if type(self.candidate_count) is not int or self.candidate_count < 1:
            raise ValueError("candidate_count must be positive")
        numeric = (self.difference, self.confidence95_low, self.confidence95_high)
        if any(not math.isfinite(float(value)) for value in numeric):
            raise ValueError("comparison statistics must be finite")
        for value in (self.relative_difference, self.standardized_effect):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("optional comparison statistics must be finite")


class FigureKind(StrEnum):
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"


@dataclass(frozen=True, slots=True)
class FigurePoint:
    x: str | float
    y: float

    def __post_init__(self) -> None:
        if isinstance(self.x, bool) or not isinstance(self.x, (str, int, float)):
            raise TypeError("figure point x must be text or numeric")
        if isinstance(self.x, str):
            _text(self.x, "figure point x")
        if isinstance(self.y, bool) or not isinstance(self.y, (int, float)) or not math.isfinite(float(self.y)):
            raise ValueError("figure point y must be finite numeric")


@dataclass(frozen=True, slots=True)
class FigureSeries:
    name: str
    points: tuple[FigurePoint, ...]

    def __post_init__(self) -> None:
        _text(self.name, "figure series name")
        if type(self.points) is not tuple or not self.points:
            raise ValueError("figure series points must be non-empty")
        if any(type(point) is not FigurePoint for point in self.points):
            raise TypeError("figure series points must contain FigurePoint")


@dataclass(frozen=True, slots=True)
class FigureSpec:
    figure_id: str
    title: str
    kind: FigureKind
    series: tuple[FigureSeries, ...]
    x_label: str = ""
    y_label: str = ""
    width: int = 800
    height: int = 480
    figure_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.figure_id, "figure id")
        _text(self.title, "figure title")
        if type(self.kind) is not FigureKind:
            raise TypeError("figure kind must be FigureKind")
        if type(self.series) is not tuple or not self.series or any(type(item) is not FigureSeries for item in self.series):
            raise TypeError("figure series must be a non-empty tuple of FigureSeries")
        if type(self.width) is not int or self.width < 240 or type(self.height) is not int or self.height < 180:
            raise ValueError("figure dimensions are too small")
        object.__setattr__(self, "figure_digest", canonical_digest({
            "id": self.figure_id, "title": self.title, "kind": self.kind.value,
            "series": self.series, "x_label": self.x_label, "y_label": self.y_label,
            "width": self.width, "height": self.height,
        }))


@dataclass(frozen=True, slots=True)
class ResearchReport:
    report_id: str
    tables: tuple[DataTable, ...] = ()
    figures: tuple[FigureSpec, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    report_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.report_id, "research report id")
        if any(type(item) is not DataTable for item in self.tables):
            raise TypeError("research report tables must contain DataTable")
        if any(type(item) is not FigureSpec for item in self.figures):
            raise TypeError("research report figures must contain FigureSpec")
        object.__setattr__(self, "report_digest", canonical_digest({
            "id": self.report_id,
            "tables": tuple(item.table_digest for item in self.tables),
            "figures": tuple(item.figure_digest for item in self.figures),
            "metadata": self.metadata,
        }))


class FigureRendererPort(Protocol):
    def render(self, figure: FigureSpec) -> str: ...


class ReportTableRendererPort(Protocol):
    def render(self, table: DataTable, format: str) -> str: ...


__all__ = [
    "DataColumn", "DataTable", "FigureKind", "FigurePoint", "FigureRendererPort",
    "FigureSeries", "FigureSpec", "GroupComparison", "MetricSummary",
    "MissingValuePolicy", "ResearchReport", "ReportTableRendererPort",
    "TableAnalysisPort", "TableReaderPort", "TableTransformPort",
]