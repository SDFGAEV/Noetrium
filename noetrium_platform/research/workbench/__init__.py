"""Aggregated downstream research workbench facade."""
from .api import (
    DataColumn, DataTable, FigureKind, FigurePoint, FigureSeries, FigureSpec,
    GroupComparison, MetricSummary, MissingValuePolicy, ResearchReport,
)
from .providers import CsvTableReader, JsonlTableReader, StandardTableRenderer, SvgFigureRenderer
from .runtime import ScientificStatistics, TablePipeline

__all__ = [
    "CsvTableReader", "DataColumn", "DataTable", "FigureKind", "FigurePoint",
    "FigureSeries", "FigureSpec", "GroupComparison", "JsonlTableReader",
    "MetricSummary", "MissingValuePolicy", "ResearchReport",
    "ScientificStatistics", "StandardTableRenderer", "SvgFigureRenderer",
    "TablePipeline",
]
