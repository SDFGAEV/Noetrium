"""Typed research-result query contracts."""

from .contracts import (
    ResearchDimension,
    ResearchDimensionKind,
    ResearchQueryGap,
    ResearchQueryGapKind,
    ResearchQuerySourceError,
    ResearchResultKind,
    ResearchResultPage,
    ResearchResultQuery,
    ResearchResultRecord,
    ResearchResultReference,
    ResearchSourceCut,
    ResearchSourceDisposition,
    ResearchSourceSnapshot,
    ResearchSourceStatus,
)
from .ports import ResearchResultQueryPort, ResearchResultSourcePort

__all__ = [
    "ResearchDimension", "ResearchDimensionKind", "ResearchQueryGap",
    "ResearchQueryGapKind", "ResearchQuerySourceError", "ResearchResultKind",
    "ResearchResultPage", "ResearchResultQuery", "ResearchResultQueryPort",
    "ResearchResultRecord", "ResearchResultReference", "ResearchResultSourcePort",
    "ResearchSourceCut", "ResearchSourceDisposition", "ResearchSourceSnapshot",
    "ResearchSourceStatus",
]
