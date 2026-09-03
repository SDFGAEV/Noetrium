"""Aggregated downstream research workbench facade."""
from .api import (
    AggregationFunction, AggregationSpec, DataColumn, DataTable, FigureCell, FigureKind, FigurePoint,
    FigureSeries, FigureSpec, GroupComparison, InferenceResult, MetricSummary,
    MissingValuePolicy, PairedComparison, ResearchReport, SplitStrategy,
)
from .providers import CsvTableReader, JsonlTableReader, StandardTableRenderer, SvgFigureRenderer
from .runtime import ScientificStatistics, TablePipeline

__all__ = [
    "AggregationFunction", "AggregationSpec", "CsvTableReader", "DataColumn", "DataTable",
    "FigureCell", "FigureKind", "FigurePoint", "FigureSeries", "FigureSpec",
    "GroupComparison", "InferenceResult", "JsonlTableReader", "MetricSummary",
    "MissingValuePolicy", "PairedComparison", "ResearchReport", "SplitStrategy",
    "ScientificStatistics", "StandardTableRenderer", "SvgFigureRenderer",
    "TablePipeline",
]
