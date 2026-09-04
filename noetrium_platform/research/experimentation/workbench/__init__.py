"""Aggregated downstream research workbench facade."""
from .api import (
    AggregationFunction, AggregationSpec, BaselineRegistryPort, BaselineSpec, DataColumn,
    DataTable, EvaluationContext, EvaluationStage, FigureCategory, FigureCell, FigureKind, FigureOutputFormat, FigurePoint,
    FigureSeries, FigureSpec, FigureStyle, GroupComparison, InferenceResult, MetricSummary,
    MissingValuePolicy, MultipleComparisonMethod, MultipleComparisonResult, PairedComparison,
    RenderedResearchPackage, ResearchEvaluation, ResearchReport, SplitStrategy,
    MeasurementRecordTableAdapter, StudyObservationTableAdapter,
)
from .providers import (
    CsvTableReader, JsonlTableReader, PdfFigureRenderer, PublicationFigureRenderer,
    StandardTableRenderer, SvgFigureRenderer,
)
from .runtime import InMemoryBaselineRegistry, ResearchFigureFactory, ResearchLifecycle, ScientificStatistics, TablePipeline

__all__ = [
    "AggregationFunction", "AggregationSpec", "BaselineRegistryPort", "BaselineSpec",
    "CsvTableReader", "DataColumn", "DataTable", "EvaluationContext", "EvaluationStage",
    "FigureCategory", "FigureCell", "FigureKind", "FigureOutputFormat", "FigurePoint", "FigureSeries", "FigureSpec", "FigureStyle",
    "GroupComparison", "InferenceResult", "JsonlTableReader", "MetricSummary",
    "MeasurementRecordTableAdapter", "MissingValuePolicy", "MultipleComparisonMethod", "MultipleComparisonResult", "PairedComparison",
    "RenderedResearchPackage", "ResearchEvaluation", "ResearchReport", "SplitStrategy",
    "StudyObservationTableAdapter", "InMemoryBaselineRegistry", "ResearchLifecycle",
    "ScientificStatistics", "PdfFigureRenderer", "PublicationFigureRenderer",
    "StandardTableRenderer", "SvgFigureRenderer",
    "TablePipeline", "ResearchFigureFactory",
]
