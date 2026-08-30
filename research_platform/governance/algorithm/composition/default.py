from __future__ import annotations

import os
from pathlib import Path

from research_platform.governance.algorithm.api import AlgorithmGovernanceApprovalSet
from research_platform.governance.algorithm.providers import (
    FilesystemAlgorithmSnapshotStore,
    FilesystemFileAnalysisCache,
    RepositorySourceInventory,
    load_algorithm_governance_approval_set,
)
from research_platform.governance.api import RepositorySourceIndexPort, RepositorySourcePort
from research_platform.governance.providers import GitRepositorySourceTree, RepositorySourceTree
from research_platform.governance.algorithm.runtime import (
    AlgorithmGovernanceService,
    AlgorithmScanner,
    JavaScriptAlgorithmAnalyzer,
    PythonAlgorithmAnalyzer,
    ShellAlgorithmAnalyzer,
    algorithm_implementation_digest,
)


def _scanner(
    source: RepositorySourcePort,
    *,
    source_index: RepositorySourceIndexPort | None,
    cache: FilesystemFileAnalysisCache | None,
    use_cache: bool,
    implementation_digest: str,
) -> AlgorithmScanner:
    authority = source_index.source_authority if source_index is not None else "filesystem"
    revision = source_index.source_revision if source_index is not None else None
    return AlgorithmScanner(
        inventory=RepositorySourceInventory(source),
        analyzers=(
            PythonAlgorithmAnalyzer(source_index),
            JavaScriptAlgorithmAnalyzer(),
            ShellAlgorithmAnalyzer(),
        ),
        cache=cache,
        use_cache=use_cache,
        source_authority=authority,
        source_revision=revision,
        analyzer_implementation_digest=implementation_digest,
    )


def _external_approval_set() -> AlgorithmGovernanceApprovalSet | None:
    path = os.environ.get("RESEARCH_PLATFORM_ALGORITHM_GOVERNANCE_APPROVALS", "").strip()
    digest = os.environ.get("RESEARCH_PLATFORM_ALGORITHM_GOVERNANCE_APPROVALS_SHA256", "").strip()
    if bool(path) != bool(digest):
        raise ValueError("external algorithm governance approval path and SHA-256 must be provided together")
    if not path:
        return None
    return load_algorithm_governance_approval_set(Path(path), expected_sha256=digest)


def build_algorithm_governance(
    root: Path,
    *,
    exact: bool = False,
    state_root: Path | None = None,
    source_inventory: RepositorySourcePort | None = None,
    source_index: RepositorySourceIndexPort | None = None,
    approval_set: AlgorithmGovernanceApprovalSet | None = None,
    git_executable: str | Path | None = None,
) -> AlgorithmGovernanceService:
    root = Path(root).resolve()
    if source_index is not None and source_inventory is not None and source_index is not source_inventory:
        raise ValueError("source_inventory and source_index must reference the same frozen source cut")
    resolved_index = source_index
    if resolved_index is None and exact:
        if source_inventory is not None:
            raise ValueError("exact algorithm governance requires a RepositorySourceIndexPort, not an unbound inventory")
        resolved_index = GitRepositorySourceTree(
            root, git_executable=git_executable
        ).index()
    source: RepositorySourcePort = resolved_index or source_inventory or RepositorySourceTree(root)
    state = Path(state_root) if state_root is not None else root / ".local" / "algorithm-governance"
    cache = None if exact else FilesystemFileAnalysisCache(state / "cache")
    implementation_digest = (
        algorithm_implementation_digest(resolved_index) if resolved_index is not None else ""
    )
    baseline_replay = None
    if exact:
        assert resolved_index is not None
        runtime_package = Path(__file__).resolve().parents[1]
        expected_package = (root / "research_platform" / "governance" / "algorithm").resolve()
        if runtime_package != expected_package:
            raise ValueError(
                "exact algorithm governance must execute the analyzer implementation from the audited repository root"
            )
        if resolved_index.source_authority != "git" or resolved_index.source_revision is None:
            raise ValueError("exact algorithm governance requires immutable Git source authority")
        filesystem_index = RepositorySourceTree(root).index()
        if algorithm_implementation_digest(filesystem_index) != implementation_digest:
            raise ValueError(
                "exact algorithm analyzer implementation bytes differ from the immutable source cut"
            )

        def replay(revision: str):
            historical = GitRepositorySourceTree(
                root, revision=revision, git_executable=git_executable
            ).index()
            return _scanner(
                historical,
                source_index=historical,
                cache=None,
                use_cache=False,
                implementation_digest=implementation_digest,
            ).scan()

        baseline_replay = replay
    scanner = _scanner(
        source,
        source_index=resolved_index,
        cache=cache,
        use_cache=not exact,
        implementation_digest=implementation_digest,
    )
    repository_baseline = root / "docs" / "status" / "algorithm" / "ALGORITHM_BASELINE.json"
    store = FilesystemAlgorithmSnapshotStore(state, baseline_path=repository_baseline)
    return AlgorithmGovernanceService(
        scanner=scanner,
        store=store,
        baseline_replay=baseline_replay,
        approval_set=approval_set if approval_set is not None else _external_approval_set(),
    )


__all__ = ["build_algorithm_governance"]
