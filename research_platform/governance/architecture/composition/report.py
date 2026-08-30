from __future__ import annotations

from pathlib import Path
import os

from research_platform.governance.api import RepositorySourceIndexPort
from research_platform.governance.providers import GitRepositorySourceTree

from ..report import (
    ArchitectureMigrationApprovalSet,
    ArchitectureReport,
    build_architecture_report as _build_architecture_report,
    load_architecture_migration_approval_set,
)


def build_architecture_report(
    root: Path,
    *,
    hotspot_limit: int = 20,
    source_index: RepositorySourceIndexPort | None = None,
    git_executable: str | Path | None = None,
    migration_approval_set: ArchitectureMigrationApprovalSet | None = None,
) -> ArchitectureReport:
    """Compose the architecture analyzer with exactly one immutable repository source cut."""

    root = Path(root).resolve()
    resolved_index = source_index or GitRepositorySourceTree(
        root, git_executable=git_executable
    ).index()
    if migration_approval_set is None:
        approval_path = os.environ.get("RESEARCH_PLATFORM_ARCHITECTURE_MIGRATION_APPROVALS", "").strip()
        approval_sha = os.environ.get("RESEARCH_PLATFORM_ARCHITECTURE_MIGRATION_APPROVALS_SHA256", "").strip()
        if bool(approval_path) != bool(approval_sha):
            raise ValueError("external architecture migration approval path and SHA-256 must be provided together")
        if approval_path:
            migration_approval_set = load_architecture_migration_approval_set(
                Path(approval_path), expected_sha256=approval_sha
            )

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
        migration_approval_set=migration_approval_set,
    )


__all__ = ["build_architecture_report"]
