from __future__ import annotations

from pathlib import Path

from research_platform.governance.api import RepositorySourceIndexPort
from research_platform.governance.providers import RepositorySourceTree

from ..report import ArchitectureReport, build_architecture_report as _build_architecture_report


def build_architecture_report(
    root: Path,
    *,
    hotspot_limit: int = 20,
    source_index: RepositorySourceIndexPort | None = None,
) -> ArchitectureReport:
    """Compose the architecture analyzer with exactly one immutable repository source cut."""

    root = Path(root).resolve()
    resolved_index = source_index or RepositorySourceTree(root).index()
    return _build_architecture_report(
        root,
        hotspot_limit=hotspot_limit,
        source_index=resolved_index,
    )


__all__ = ["build_architecture_report"]
