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


def _schema_accepts(data_type: str, value: JsonValue) -> bool:
    if data_type == "unknown":
        return True
    if data_type in {"text", "string"}:
        return type(value) is str
    if data_type in {"int", "integer"}:
        return type(value) is int
    if data_type in {"float", "number", "numeric"}:
        return type(value) in {int, float}
    if data_type in {"bool", "boolean"}:
        return type(value) is bool
    return True


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
            frozen = tuple(freeze_json(value) for value in row)
            for column, value in zip(self.columns, frozen, strict=True):
                if value is None:
                    if not column.nullable:
                        raise ValueError(f"non-nullable column {column.name!r} contains null")
                elif not _schema_accepts(column.data_type.lower(), value):
                    raise TypeError(f"column {column.name!r} rejects value for data_type {column.data_type!r}")
            frozen_rows.append(frozen)
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
        if any(type(item) is not tuple or len(item) != 2 or type(item[0]) is not str or not item[0].strip() or type(item[1]) is not str for item in self.metadata):
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


class SplitStrategy(StrEnum):
    RANDOM = "random"
    STRATIFIED = "stratified"
    GROUP = "group"
    TEMPORAL = "temporal"


class EvaluationStage(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    TEST = "test"
    SHADOW = "shadow"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Immutable identity shared by every paper evaluation and comparison."""

    project_id: str
    experiment_id: str
    study_id: str
    candidate_id: str
    stage: EvaluationStage
    dataset_digest: str
    split_digest: str
    protocol_digest: str
    code_commit: str
    configuration_digest: str
    seed: str
    baseline_id: str | None = None
    run_id: str | None = None
    context_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("project_id", self.project_id), ("experiment_id", self.experiment_id),
            ("study_id", self.study_id), ("candidate_id", self.candidate_id),
            ("code_commit", self.code_commit), ("seed", self.seed),
        ):
            _text(value, f"evaluation context {name}")
        if not isinstance(self.stage, EvaluationStage):
            raise TypeError("evaluation context stage must be EvaluationStage")
        for name, value in (
            ("dataset_digest", self.dataset_digest),
            ("split_digest", self.split_digest),
            ("protocol_digest", self.protocol_digest),
            ("configuration_digest", self.configuration_digest),
        ):
            _sha(value, f"evaluation context {name}")
        if self.baseline_id is not None:
            _text(self.baseline_id, "evaluation context baseline_id")
        if self.run_id is not None:
            _text(self.run_id, "evaluation context run_id")
        object.__setattr__(self, "context_digest", canonical_digest({
            "project_id": self.project_id, "experiment_id": self.experiment_id,
            "study_id": self.study_id, "candidate_id": self.candidate_id,
            "stage": self.stage.value, "dataset_digest": self.dataset_digest,
            "split_digest": self.split_digest, "protocol_digest": self.protocol_digest,
            "code_commit": self.code_commit, "configuration_digest": self.configuration_digest,
            "seed": self.seed, "baseline_id": self.baseline_id, "run_id": self.run_id,
        }))

    @property
    def locked(self) -> bool:
        return self.stage in {EvaluationStage.TEST, EvaluationStage.SHADOW, EvaluationStage.LIVE}


@dataclass(frozen=True, slots=True)
class BaselineSpec:
    """One canonical reference method; downstream code must not redefine it."""

    baseline_id: str
    implementation_id: str
    configuration_digest: str
    dataset_digest: str
    protocol_digest: str
    description: str = ""
    baseline_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.baseline_id, "baseline baseline_id")
        _text(self.implementation_id, "baseline implementation_id")
        _sha(self.configuration_digest, "baseline configuration_digest")
        _sha(self.dataset_digest, "baseline dataset_digest")
        _sha(self.protocol_digest, "baseline protocol_digest")
        if type(self.description) is not str:
            raise TypeError("baseline description must be a string")
        object.__setattr__(self, "baseline_digest", canonical_digest({
            "baseline_id": self.baseline_id, "implementation_id": self.implementation_id,
            "configuration_digest": self.configuration_digest,
            "dataset_digest": self.dataset_digest, "protocol_digest": self.protocol_digest,
            "description": self.description,
        }))


class BaselineRegistryPort(Protocol):
    def register(self, baseline: BaselineSpec) -> BaselineSpec: ...

    def resolve(self, baseline_id: str) -> BaselineSpec: ...

    def validate(self, context: EvaluationContext) -> None: ...


class AggregationFunction(StrEnum):
    COUNT = "count"
    SUM = "sum"
    MEAN = "mean"
    VARIANCE = "variance"
    STANDARD_DEVIATION = "standard_deviation"
    MINIMUM = "minimum"
    MEDIAN = "median"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class AggregationSpec:
    output_name: str
    function: AggregationFunction
    source_column: str | None = None
    data_type: str = "float"

    def __post_init__(self) -> None:
        _text(self.output_name, "aggregation output_name")
        if not isinstance(self.function, AggregationFunction):
            raise TypeError("aggregation function must be AggregationFunction")
        if self.function is AggregationFunction.COUNT and self.source_column is not None:
            _text(self.source_column, "aggregation source_column")
        elif self.function is not AggregationFunction.COUNT:
            _text(self.source_column, "aggregation source_column")
        _text(self.data_type, "aggregation data_type")


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
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) for value in numeric):
            raise ValueError("comparison statistics must be finite")
        if self.confidence95_low > self.confidence95_high:
            raise ValueError("comparison confidence interval is invalid")
        for value in (self.relative_difference, self.standardized_effect):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                raise ValueError("optional comparison statistics must be finite")


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Backend-neutral inferential result; advanced scientific backends may enrich it."""

    metric: str
    method: str
    sample_count: int
    estimate: float
    standard_error: float
    confidence95_low: float
    confidence95_high: float
    p_value: float | None = None
    effect_size: float | None = None
    null_value: float = 0.0

    def __post_init__(self) -> None:
        _text(self.metric, "inference metric")
        _text(self.method, "inference method")
        if type(self.sample_count) is not int or self.sample_count < 1:
            raise ValueError("inference sample_count must be positive")
        numeric = (self.estimate, self.standard_error, self.confidence95_low,
                   self.confidence95_high, self.null_value)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in numeric):
            raise ValueError("inference values must be finite numeric")
        if self.standard_error < 0 or self.confidence95_low > self.confidence95_high:
            raise ValueError("inference uncertainty values are invalid")
        if self.p_value is not None and (isinstance(self.p_value, bool) or not isinstance(self.p_value, (int, float)) or not 0.0 <= float(self.p_value) <= 1.0):
            raise ValueError("inference p_value must be between zero and one")
        if self.effect_size is not None and (isinstance(self.effect_size, bool) or not isinstance(self.effect_size, (int, float)) or not math.isfinite(float(self.effect_size))):
            raise ValueError("inference effect_size must be finite")


@dataclass(frozen=True, slots=True)
class PairedComparison:
    """Paired-unit comparison for seeds, users, tasks, episodes, or scenarios."""

    metric: str
    pair_column: str
    count: int
    mean_difference: float
    standard_deviation: float
    standard_error: float
    confidence95_low: float
    confidence95_high: float
    p_value: float | None = None
    standardized_effect: float | None = None

    def __post_init__(self) -> None:
        _text(self.metric, "paired comparison metric")
        _text(self.pair_column, "paired comparison pair_column")
        if type(self.count) is not int or self.count < 1:
            raise ValueError("paired comparison count must be positive")
        numeric = (self.mean_difference, self.standard_deviation, self.standard_error,
                   self.confidence95_low, self.confidence95_high)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in numeric):
            raise ValueError("paired comparison values must be finite numeric")
        if self.standard_deviation < 0 or self.standard_error < 0 or self.confidence95_low > self.confidence95_high:
            raise ValueError("paired comparison uncertainty values are invalid")
        if self.p_value is not None and (isinstance(self.p_value, bool) or not isinstance(self.p_value, (int, float)) or not 0.0 <= float(self.p_value) <= 1.0):
            raise ValueError("paired comparison p_value must be between zero and one")
        if self.standardized_effect is not None and (isinstance(self.standardized_effect, bool) or not isinstance(self.standardized_effect, (int, float)) or not math.isfinite(float(self.standardized_effect))):
            raise ValueError("paired comparison standardized_effect must be finite")


class FigureKind(StrEnum):
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOXPLOT = "boxplot"
    HEATMAP = "heatmap"


@dataclass(frozen=True, slots=True)
class FigurePoint:
    x: str | float
    y: float
    error_low: float | None = None
    error_high: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.x, bool) or not isinstance(self.x, (str, int, float)):
            raise TypeError("figure point x must be text or numeric")
        if isinstance(self.x, str):
            _text(self.x, "figure point x")
        if isinstance(self.y, bool) or not isinstance(self.y, (int, float)) or not math.isfinite(float(self.y)):
            raise ValueError("figure point y must be finite numeric")
        for name, value in (("error_low", self.error_low), ("error_high", self.error_high)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                raise ValueError(f"figure point {name} must be finite numeric or None")
        if (self.error_low is None) != (self.error_high is None):
            raise ValueError("figure point error_low and error_high must be provided together")
        if self.error_low is not None and self.error_low > self.error_high:
            raise ValueError("figure point error bounds are invalid")


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
class FigureCell:
    row: str | float
    column: str | float
    value: float

    def __post_init__(self) -> None:
        if isinstance(self.row, bool) or not isinstance(self.row, (str, int, float)):
            raise TypeError("figure cell row must be text or numeric")
        if isinstance(self.column, bool) or not isinstance(self.column, (str, int, float)):
            raise TypeError("figure cell column must be text or numeric")
        if isinstance(self.row, str):
            _text(self.row, "figure cell row")
        if isinstance(self.column, str):
            _text(self.column, "figure cell column")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(float(self.value)):
            raise ValueError("figure cell value must be finite numeric")


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
    cells: tuple[FigureCell, ...] = ()
    caption: str = ""
    source_digests: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    figure_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.figure_id, "figure id")
        _text(self.title, "figure title")
        if type(self.kind) is not FigureKind:
            raise TypeError("figure kind must be FigureKind")
        if type(self.series) is not tuple or any(type(item) is not FigureSeries for item in self.series):
            raise TypeError("figure series must be a tuple of FigureSeries")
        if not self.series and self.kind is not FigureKind.HEATMAP:
            raise ValueError("non-heatmap figures require at least one series")
        if type(self.width) is not int or self.width < 240 or type(self.height) is not int or self.height < 180:
            raise ValueError("figure dimensions are too small")
        if type(self.cells) is not tuple or any(type(item) is not FigureCell for item in self.cells):
            raise TypeError("figure cells must contain FigureCell")
        if self.kind is FigureKind.HEATMAP and not self.cells:
            raise ValueError("heatmap figures require cells")
        if type(self.caption) is not str or type(self.source_digests) is not tuple or type(self.metadata) is not tuple:
            raise TypeError("figure caption, source_digests, and metadata have invalid types")
        for digest in self.source_digests:
            _sha(digest, "figure source digest")
        if len(set(self.source_digests)) != len(self.source_digests):
            raise ValueError("figure source_digests must be unique")
        if any(type(item) is not tuple or len(item) != 2 or type(item[0]) is not str or not item[0].strip() or type(item[1]) is not str for item in self.metadata):
            raise ValueError("figure metadata must contain string key/value pairs")
        if len({item[0] for item in self.metadata}) != len(self.metadata):
            raise ValueError("figure metadata keys must be unique")
        object.__setattr__(self, "figure_digest", canonical_digest({
            "id": self.figure_id, "title": self.title, "kind": self.kind.value,
            "series": self.series, "cells": self.cells, "x_label": self.x_label, "y_label": self.y_label,
            "width": self.width, "height": self.height, "caption": self.caption,
            "source_digests": self.source_digests, "metadata": self.metadata,
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
        if len({item.table_id for item in self.tables}) != len(self.tables):
            raise ValueError("research report table ids must be unique")
        if len({item.figure_id for item in self.figures}) != len(self.figures):
            raise ValueError("research report figure ids must be unique")
        if type(self.metadata) is not tuple or any(type(item) is not tuple or len(item) != 2 or type(item[0]) is not str or not item[0].strip() or type(item[1]) is not str for item in self.metadata):
            raise ValueError("research report metadata must contain string key/value pairs")
        object.__setattr__(self, "report_digest", canonical_digest({
            "id": self.report_id,
            "tables": tuple(item.table_digest for item in self.tables),
            "figures": tuple(item.figure_digest for item in self.figures),
            "metadata": self.metadata,
        }))


@dataclass(frozen=True, slots=True)
class ResearchEvaluation:
    """Complete, identity-bound evaluation projection for downstream authors."""

    context: EvaluationContext
    table: DataTable
    summaries: tuple[MetricSummary, ...]
    comparison: GroupComparison | None
    report: ResearchReport
    evaluation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.context) is not EvaluationContext:
            raise TypeError("research evaluation context must be EvaluationContext")
        if type(self.table) is not DataTable:
            raise TypeError("research evaluation table must be DataTable")
        if type(self.summaries) is not tuple or any(type(item) is not MetricSummary for item in self.summaries):
            raise TypeError("research evaluation summaries must contain MetricSummary")
        if self.comparison is not None and type(self.comparison) is not GroupComparison:
            raise TypeError("research evaluation comparison must be GroupComparison or None")
        if type(self.report) is not ResearchReport:
            raise TypeError("research evaluation report must be ResearchReport")
        if self.table.table_digest not in {
            digest for figure in self.report.figures for digest in figure.source_digests
        } and self.report.tables != (self.table,):
            raise ValueError("research evaluation report must retain the evaluated table lineage")
        object.__setattr__(self, "evaluation_digest", canonical_digest({
            "context": self.context.context_digest,
            "table": self.table.table_digest,
            "summaries": self.summaries,
            "comparison": self.comparison,
            "report": self.report.report_digest,
        }))


class FigureRendererPort(Protocol):
    def render(self, figure: FigureSpec) -> str: ...


class ReportTableRendererPort(Protocol):
    def render(self, table: DataTable, format: str) -> str: ...


__all__ = [
    "AggregationFunction", "AggregationSpec", "BaselineRegistryPort", "BaselineSpec",
    "DataColumn", "DataTable", "EvaluationContext", "EvaluationStage",
    "FigureCell", "FigureKind", "FigurePoint", "FigureRendererPort",
    "FigureSeries", "FigureSpec", "GroupComparison", "InferenceResult", "MetricSummary",
    "MissingValuePolicy", "PairedComparison", "ResearchEvaluation", "ResearchReport",
    "ReportTableRendererPort", "SplitStrategy",
    "TableAnalysisPort", "TableReaderPort", "TableTransformPort",
]