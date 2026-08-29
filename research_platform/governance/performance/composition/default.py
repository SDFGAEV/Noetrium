from __future__ import annotations

from pathlib import Path

from research_platform.governance.api import RepositorySourceIndexPort, RepositorySourcePort
from research_platform.governance.performance.providers import (
    FilesystemPerformanceSnapshotStore,
    RepositoryPerformanceSourceInventory,
)
from research_platform.governance.performance.runtime import (
    JavaScriptPerformanceAnalyzer,
    PerformanceGovernanceService,
    PerformanceScanner,
    PythonPerformanceAnalyzer,
    ShellPerformanceAnalyzer,
)
from research_platform.governance.providers import RepositorySourceTree


def build_performance_governance(
    root: Path,
    *,
    state_root: Path | None = None,
    source_inventory: RepositorySourcePort | None = None,
    source_index: RepositorySourceIndexPort | None = None,
) -> PerformanceGovernanceService:
    root = Path(root).resolve()
    if source_index is not None and source_inventory is not None and source_index is not source_inventory:
        raise ValueError("source_inventory and source_index must reference the same frozen source cut")
    source = source_index or source_inventory or RepositorySourceTree(root)
    state = Path(state_root) if state_root is not None else root / ".local" / "performance-governance"
    scanner = PerformanceScanner(
        RepositoryPerformanceSourceInventory(source),
        (
            PythonPerformanceAnalyzer(source_index),
            JavaScriptPerformanceAnalyzer(),
            ShellPerformanceAnalyzer(),
        ),
    )
    store = FilesystemPerformanceSnapshotStore(
        state,
        baseline_path=root / "docs" / "status" / "performance" / "PERFORMANCE_BASELINE.json",
    )
    return PerformanceGovernanceService(scanner, store)


__all__ = ["build_performance_governance"]
