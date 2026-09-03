"""Aggregated downstream research workbench facade."""
from .api import (
    AggregationFunction, AggregationSpec, BaselineRegistryPort, BaselineSpec, DataColumn,
    DataTable, EvaluationContext, EvaluationStage, FigureCell, FigureKind, FigurePoint,
    FigureSeries, FigureSpec, GroupComparison, InferenceResult, MetricSummary,
    MissingValuePolicy, PairedComparison, RenderedResearchPackage, ResearchEvaluation, ResearchReport, SplitStrategy,
)
from .providers import (
    CsvTableReader, JsonlTableReader, MeasurementRecordTableAdapter,
    StandardTableRenderer, StudyObservationTableAdapter, SvgFigureRenderer,
)
from .runtime import InMemoryBaselineRegistry, ResearchLifecycle, ScientificStatistics, TablePipeline

__all__ = [
    "AggregationFunction", "AggregationSpec", "BaselineRegistryPort", "BaselineSpec",
    "CsvTableReader", "DataColumn", "DataTable", "EvaluationContext", "EvaluationStage",
    "FigureCell", "FigureKind", "FigurePoint", "FigureSeries", "FigureSpec",
    "GroupComparison", "InferenceResult", "JsonlTableReader", "MetricSummary",
    "MeasurementRecordTableAdapter", "MissingValuePolicy", "PairedComparison",
    "RenderedResearchPackage", "ResearchEvaluation", "ResearchReport", "SplitStrategy",
    "StudyObservationTableAdapter", "InMemoryBaselineRegistry", "ResearchLifecycle",
    "ScientificStatistics", "StandardTableRenderer", "SvgFigureRenderer",
    "TablePipeline",
]
