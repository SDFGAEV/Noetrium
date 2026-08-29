from __future__ import annotations

from pathlib import Path

from research_platform.governance.algorithm.providers import (
    FilesystemAlgorithmSnapshotStore,
    FilesystemFileAnalysisCache,
    RepositorySourceInventory,
)
from research_platform.governance.api import RepositorySourceIndexPort, RepositorySourcePort
from research_platform.governance.providers import RepositorySourceTree
from research_platform.governance.algorithm.runtime import (
    AlgorithmGovernanceService,
    AlgorithmScanner,
    JavaScriptAlgorithmAnalyzer,
    PythonAlgorithmAnalyzer,
    ShellAlgorithmAnalyzer,
)


def build_algorithm_governance(
    root: Path,
    *,
    exact: bool = False,
    state_root: Path | None = None,
    source_inventory: RepositorySourcePort | None = None,
    source_index: RepositorySourceIndexPort | None = None,
) -> AlgorithmGovernanceService:
    root = Path(root).resolve()
    if source_index is not None and source_inventory is not None and source_index is not source_inventory:
        raise ValueError("source_inventory and source_index must reference the same frozen source cut")
    source = source_index or source_inventory or RepositorySourceTree(root)
    state = Path(state_root) if state_root is not None else root / ".local" / "algorithm-governance"
    cache = None if exact else FilesystemFileAnalysisCache(state / "cache")
    scanner = AlgorithmScanner(
        inventory=RepositorySourceInventory(source),
        analyzers=(PythonAlgorithmAnalyzer(source_index), JavaScriptAlgorithmAnalyzer(), ShellAlgorithmAnalyzer()),
        cache=cache,
        use_cache=not exact,
    )
    # Baseline is a reviewed repository artifact; current/history stay in local durable state.
    repository_baseline = root / "docs" / "status" / "algorithm" / "ALGORITHM_BASELINE.json"
    store = FilesystemAlgorithmSnapshotStore(state, baseline_path=repository_baseline)
    return AlgorithmGovernanceService(scanner=scanner, store=store)


__all__ = ["build_algorithm_governance"]
