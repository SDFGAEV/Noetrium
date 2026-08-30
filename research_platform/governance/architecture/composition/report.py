from __future__ import annotations

from pathlib import Path

from research_platform.governance.api import RepositorySourceIndexPort
from research_platform.governance.providers import GitRepositorySourceTree

from ..report import ArchitectureReport, build_architecture_report as _build_architecture_report


def build_architecture_report(
    root: Path,
    *,
    hotspot_limit: int = 20,
    source_index: RepositorySourceIndexPort | None = None,
    git_executable: str | Path | None = None,
) -> ArchitectureReport:
    """Compose the architecture analyzer with exactly one immutable repository source cut."""

    root = Path(root).resolve()
    resolved_index = source_index or GitRepositorySourceTree(
        root, git_executable=git_executable
    ).index()
    historical_factory = None
    if resolved_index.source_authority == "git":
        historical_factory = lambda revision: GitRepositorySourceTree(
            root, revision=revision, git_executable=git_executable
        ).index()
    return _build_architecture_report(
        root,
        hotspot_limit=hotspot_limit,
        source_index=resolved_index,
        historical_source_index_factory=historical_factory,
    )


__all__ = ["build_architecture_report"]
