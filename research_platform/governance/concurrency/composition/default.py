from __future__ import annotations

from pathlib import Path

from research_platform.governance.api import RepositorySourceIndexPort, RepositorySourcePort
from research_platform.governance.concurrency.providers import (
    FilesystemConcurrencySnapshotStore,
    RepositoryConcurrencySourceInventory,
)
from research_platform.governance.concurrency.runtime import (
    ConcurrencyGovernanceService,
    ConcurrencyScanner,
    JavaScriptConcurrencyAnalyzer,
    PythonConcurrencyAnalyzer,
    ShellConcurrencyAnalyzer,
)
from research_platform.governance.providers import RepositorySourceTree


def build_concurrency_governance(
    root: Path,
    *,
    state_root: Path | None = None,
    source_inventory: RepositorySourcePort | None = None,
    source_index: RepositorySourceIndexPort | None = None,
) -> ConcurrencyGovernanceService:
    root = Path(root).resolve()
    if source_index is not None and source_inventory is not None and source_index is not source_inventory:
        raise ValueError("source_inventory and source_index must reference the same frozen source cut")
    source = source_index or source_inventory or RepositorySourceTree(root)
    state = Path(state_root) if state_root is not None else root / ".local" / "concurrency-governance"
    scanner = ConcurrencyScanner(
        RepositoryConcurrencySourceInventory(source),
        (
            PythonConcurrencyAnalyzer(source_index),
            JavaScriptConcurrencyAnalyzer(),
            ShellConcurrencyAnalyzer(),
        ),
    )
    store = FilesystemConcurrencySnapshotStore(
        state,
        baseline_path=root / "docs" / "governance" / "CONCURRENCY_BASELINE.json",
    )
    return ConcurrencyGovernanceService(scanner, store)


__all__ = ["build_concurrency_governance"]
