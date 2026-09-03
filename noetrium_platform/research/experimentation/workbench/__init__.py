"""Aggregated downstream research workbench facade."""
from .api import (
    AggregationFunction, AggregationSpec, BaselineRegistryPort, BaselineSpec, DataColumn,
    DataTable, EvaluationContext, EvaluationStage, FigureCell, FigureKind, FigurePoint,
    FigureSeries, FigureSpec, FigureStyle, GroupComparison, InferenceResult, MetricSummary,
    MissingValuePolicy, MultipleComparisonMethod, MultipleComparisonResult, PairedComparison,
    RenderedResearchPackage, ResearchEvaluation, ResearchReport, SplitStrategy,
    MeasurementRecordTableAdapter, StudyObservationTableAdapter,
)
from .providers import (
    CsvTableReader, JsonlTableReader, StandardTableRenderer, SvgFigureRenderer,
)
from .runtime import InMemoryBaselineRegistry, ResearchFigureFactory, ResearchLifecycle, ScientificStatistics, TablePipeline

__all__ = [
    "AggregationFunction", "AggregationSpec", "BaselineRegistryPort", "BaselineSpec",
    "CsvTableReader", "DataColumn", "DataTable", "EvaluationContext", "EvaluationStage",
    "FigureCell", "FigureKind", "FigurePoint", "FigureSeries", "FigureSpec", "FigureStyle",
    "GroupComparison", "InferenceResult", "JsonlTableReader", "MetricSummary",
    "MeasurementRecordTableAdapter", "MissingValuePolicy", "MultipleComparisonMethod", "MultipleComparisonResult", "PairedComparison",
    "RenderedResearchPackage", "ResearchEvaluation", "ResearchReport", "SplitStrategy",
    "StudyObservationTableAdapter", "InMemoryBaselineRegistry", "ResearchLifecycle",
    "ScientificStatistics", "StandardTableRenderer", "SvgFigureRenderer",
    "TablePipeline", "ResearchFigureFactory",
]
