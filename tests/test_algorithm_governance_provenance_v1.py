from __future__ import annotations

from pathlib import Path

import pytest

from noetrium_platform.foundation.governance.algorithm.api import AlgorithmLanguage, SourceDocument
from noetrium_platform.foundation.governance.algorithm.providers import (
    FilesystemFileAnalysisCache,
    RepositorySourceInventory,
)
from noetrium_platform.foundation.governance.algorithm.runtime import (
    AlgorithmGovernanceService,
    AlgorithmScanner,
    PythonAlgorithmAnalyzer,
    gate_against_baseline,
)
from noetrium_platform.foundation.governance.providers import RepositorySourceTree


def _algorithm_test_git_executable() -> str:
    import os
    import shutil
    configured = os.environ.get("NOETRIUM_GIT_EXECUTABLE", "").strip()
    executable = configured or shutil.which("git")
    if not executable:
        pytest.skip("Git executable is required for immutable algorithm provenance tests")
    return executable


def _algorithm_snapshot_with_complexity(
    complexity: str,
    *,
    source_revision: str,
    source_digest: str,
    implementation_digest: str,
):
    from noetrium_platform.foundation.governance.algorithm.api import (
        AlgorithmMetrics,
        AlgorithmSnapshot,
        AlgorithmSymbol,
    )
    symbol = AlgorithmSymbol(
        symbol_id="pkg/a.py::f",
        relative_path="pkg/a.py",
        language=AlgorithmLanguage.PYTHON,
        qualified_name="f",
        line_start=1,
        line_end=2,
        metrics=AlgorithmMetrics(estimated_complexity=complexity),
    )
    return AlgorithmSnapshot(
        schema_version="algorithm-snapshot.v3",
        analyzer_revision="python:test-v1",
        source_digest=source_digest,
        symbols=(symbol,),
        coverage=(),
        generated_unix_ns=1,
        source_authority="git",
        source_revision=source_revision,
        analyzer_implementation_digest=implementation_digest,
    )




def _approval_set(*, baselines=(), complexity=()):
    from noetrium_platform.foundation.governance.algorithm.api import AlgorithmGovernanceApprovalSet
    return AlgorithmGovernanceApprovalSet(
        schema_version="algorithm-governance-approval-set.v1",
        authority="ROLE00",
        baseline_approvals=tuple(baselines),
        complexity_migrations=tuple(complexity),
        default_decision="not_approved",
        rule="Exact source and analyzer identity only.",
    )

def test_algorithm_immutable_git_replay_is_semantically_reproducible(tmp_path: Path) -> None:
    import subprocess
    from noetrium_platform.foundation.governance.algorithm.runtime import algorithm_snapshot_semantic_digest
    from noetrium_platform.foundation.governance.providers import GitRepositorySourceTree

    git = _algorithm_test_git_executable()
    def run(*args: str) -> str:
        completed = subprocess.run(
            [git, "-C", str(tmp_path), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
        )
        return completed.stdout.strip()
    run("init")
    run("config", "user.email", "role01-algorithm-test@example.invalid")
    run("config", "user.name", "ROLE01 Algorithm Test")
    source = tmp_path / "pkg" / "a.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f(rows):\n    return len(rows)\n", encoding="utf-8")
    run("add", "."); run("commit", "-m", "baseline")
    baseline_sha = run("rev-parse", "HEAD")
    baseline_index = GitRepositorySourceTree(
        tmp_path, revision=baseline_sha, git_executable=git
    ).index()
    implementation_digest = "d" * 64
    def scan(index):
        return AlgorithmScanner(
            inventory=RepositorySourceInventory(index),
            analyzers=(PythonAlgorithmAnalyzer(index),),
            source_authority=index.source_authority,
            source_revision=index.source_revision,
            analyzer_implementation_digest=implementation_digest,
        ).scan()
    baseline = scan(baseline_index)
    source.write_text("def f(rows):\n    for row in rows:\n        print(row)\n", encoding="utf-8")
    run("add", "."); run("commit", "-m", "candidate")
    replay_index = GitRepositorySourceTree(
        tmp_path, revision=baseline_sha, git_executable=git
    ).index()
    replayed = scan(replay_index)
    assert baseline.source_revision == baseline_sha
    assert replayed.source_revision == baseline_sha
    assert baseline.source_digest == replayed.source_digest
    assert algorithm_snapshot_semantic_digest(baseline) == algorithm_snapshot_semantic_digest(replayed)


def test_algorithm_service_reports_one_parent_blocker_for_legacy_baseline() -> None:
    from types import SimpleNamespace
    from noetrium_platform.foundation.governance.algorithm.api import AlgorithmSnapshot

    current = _algorithm_snapshot_with_complexity(
        "O(N)",
        source_revision="2" * 40,
        source_digest="3" * 64,
        implementation_digest="4" * 64,
    )
    legacy = AlgorithmSnapshot(
        schema_version="algorithm-snapshot.v2",
        analyzer_revision=current.analyzer_revision,
        source_digest="5" * 64,
        symbols=current.symbols,
        coverage=(),
        generated_unix_ns=1,
        source_authority="legacy",
        source_revision=None,
        analyzer_implementation_digest="",
    )
    store = SimpleNamespace(
        load_baseline=lambda: legacy,
        publish_current=lambda _snapshot: None,
        append_history=lambda _snapshot: None,
        publish_baseline=lambda _snapshot: None,
    )
    service = AlgorithmGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current),
        store=store,
        baseline_replay=lambda _revision: legacy,
    )
    _snapshot, report = service.gate()
    assert not report.passed
    assert len(report.blockers) == 1
    assert "baseline provenance migration required" in report.blockers[0]
    assert report.diff.added == report.diff.removed == report.diff.changed == report.diff.moved == ()


def test_algorithm_analyzer_identity_mismatch_blocks_before_symbol_diff() -> None:
    from noetrium_platform.foundation.governance.algorithm.runtime import baseline_provenance_blocker

    baseline = _algorithm_snapshot_with_complexity(
        "O(1)",
        source_revision="1" * 40,
        source_digest="2" * 64,
        implementation_digest="3" * 64,
    )
    current = _algorithm_snapshot_with_complexity(
        "O(N^2)",
        source_revision="4" * 40,
        source_digest="5" * 64,
        implementation_digest="6" * 64,
    )
    blocker = baseline_provenance_blocker(baseline, current, replay=lambda _revision: baseline)
    assert blocker is not None
    assert "analyzer implementation migration required" in blocker


def test_algorithm_baseline_replay_mismatch_fails_closed() -> None:
    from dataclasses import replace
    from noetrium_platform.foundation.governance.algorithm.runtime import baseline_provenance_blocker

    baseline = _algorithm_snapshot_with_complexity(
        "O(1)",
        source_revision="1" * 40,
        source_digest="2" * 64,
        implementation_digest="3" * 64,
    )
    current = replace(
        baseline,
        source_revision="4" * 40,
        source_digest="5" * 64,
    )
    replayed = replace(
        baseline,
        symbols=(_algorithm_snapshot_with_complexity(
            "O(N)",
            source_revision="1" * 40,
            source_digest="2" * 64,
            implementation_digest="3" * 64,
        ).symbols[0],),
    )
    blocker = baseline_provenance_blocker(baseline, current, replay=lambda _revision: replayed)
    assert blocker == "algorithm baseline metrics are not reproducible from exact Git source and analyzer identity"


def test_exact_lower_bound_approval_allows_only_its_bound_complexity_transition() -> None:
    from dataclasses import replace
    from noetrium_platform.foundation.governance.algorithm.api import AlgorithmComplexityMigrationApproval

    baseline = _algorithm_snapshot_with_complexity(
        "O(1)",
        source_revision="1" * 40,
        source_digest="2" * 64,
        implementation_digest="3" * 64,
    )
    current = _algorithm_snapshot_with_complexity(
        "O(N)",
        source_revision="4" * 40,
        source_digest="5" * 64,
        implementation_digest="3" * 64,
    )
    approval = AlgorithmComplexityMigrationApproval(
        migration_id="algorithm-lower-bound-001",
        symbol_id="pkg/a.py::f",
        source_git_sha=current.source_revision or "",
        source_digest=current.source_digest,
        analyzer_revision=current.analyzer_revision,
        analyzer_implementation_digest=current.analyzer_implementation_digest,
        old_complexity="O(1)",
        new_complexity="O(N)",
        decision="approved",
        authority="ROLE00",
        scope="algorithm-complexity-lower-bound",
        review_state="reviewed",
        review_evidence_refs=("state/evidence.json",),
        issued_at="2026-08-30T22:00:00+08:00",
        rationale="Returning N typed records requires linear result construction and this proof is source-bound.",
        approval_record_sha256="6" * 64,
    )
    approved = gate_against_baseline(
        baseline, current, approval_set=_approval_set(complexity=(approval,))
    )
    assert approved.passed
    assert any("approved lower-bound complexity migration" in row for row in approved.warnings)
    stale = replace(approval, source_git_sha="7" * 40)
    rejected = gate_against_baseline(
        baseline, current, approval_set=_approval_set(complexity=(stale,))
    )
    assert not rejected.passed
    assert any("complexity regression" in row for row in rejected.blockers)


def test_git_baseline_acceptance_requires_exact_role00_approval() -> None:
    from types import SimpleNamespace
    from noetrium_platform.foundation.governance.algorithm.api import (
        AlgorithmBaselineApproval,
        AlgorithmGovernanceApprovalSet,
    )
    from noetrium_platform.foundation.governance.algorithm.runtime import (
        AlgorithmBaselineApprovalMissing,
        algorithm_snapshot_semantic_digest,
    )

    current = _algorithm_snapshot_with_complexity(
        "O(N)",
        source_revision="1" * 40,
        source_digest="2" * 64,
        implementation_digest="3" * 64,
    )
    saved = []
    store = SimpleNamespace(
        load_baseline=lambda: None,
        publish_current=lambda _snapshot: None,
        append_history=lambda _snapshot: None,
        publish_baseline=lambda snapshot: saved.append(snapshot),
    )
    scanner = SimpleNamespace(scan=lambda: current)
    service = AlgorithmGovernanceService(
        scanner=scanner, store=store, baseline_replay=lambda _revision: current
    )
    with pytest.raises(AlgorithmBaselineApprovalMissing, match="historical source revision"):
        service.accept_baseline()
    with pytest.raises(AlgorithmBaselineApprovalMissing, match="ROLE00 exact"):
        service.accept_baseline(source_revision=current.source_revision)
    approval = AlgorithmBaselineApproval(
        approval_id="algorithm-baseline-001",
        source_git_sha=current.source_revision or "",
        source_digest=current.source_digest,
        analyzer_revision=current.analyzer_revision,
        analyzer_implementation_digest=current.analyzer_implementation_digest,
        snapshot_digest=algorithm_snapshot_semantic_digest(current),
        decision="approved",
        authority="ROLE00",
        scope="algorithm-baseline-refresh",
        review_state="reviewed",
        review_evidence_refs=("state/baseline-review.json",),
        issued_at="2026-08-30T22:00:00+08:00",
        note="Reviewed immutable analyzer and source replay evidence.",
        approval_record_sha256="4" * 64,
    )
    service.approval_set = _approval_set(baselines=(approval,))
    assert service.accept_baseline(source_revision=current.source_revision) == current
    assert saved == [current]


def test_algorithm_external_approval_set_is_file_and_record_digest_bound(tmp_path: Path) -> None:
    import hashlib
    import json
    from noetrium_platform.foundation.governance.algorithm.providers import (
        AlgorithmGovernanceApprovalError,
        load_algorithm_governance_approval_set,
    )

    record = {
        "schema": "algorithm-baseline-approval.v1",
        "approval_id": "algorithm-baseline-001",
        "source_sha": "1" * 40,
        "source_digest": "2" * 64,
        "analyzer_revision": "python:test-v1",
        "analyzer_implementation_digest": "3" * 64,
        "snapshot_digest": "4" * 64,
        "decision": "approved",
        "authority": "ROLE00",
        "scope": "algorithm-baseline-refresh",
        "review_state": "reviewed",
        "review_evidence_refs": ["state/review.json"],
        "issued_at": "2026-08-30T22:00:00+08:00",
        "note": "Reviewed exact immutable replay candidate.",
    }
    record["approval_record_sha256"] = hashlib.sha256(json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    document = {
        "schema": "algorithm-governance-approval-set.v1",
        "authority": "ROLE00",
        "approvals": [record],
        "default_decision": "not_approved",
        "rule": "Stale or mismatched approvals grant zero authority.",
    }
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = tmp_path / "approvals.json"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    loaded = load_algorithm_governance_approval_set(path, expected_sha256=digest)
    assert loaded.authority == "ROLE00"
    assert loaded.baseline_approvals[0].source_git_sha == "1" * 40
    path.write_bytes(raw + b" ")
    with pytest.raises(AlgorithmGovernanceApprovalError, match="approval set digest mismatch"):
        load_algorithm_governance_approval_set(path, expected_sha256=digest)



def test_algorithm_cache_key_includes_analyzer_implementation_identity(tmp_path: Path) -> None:
    from dataclasses import replace

    source = tmp_path / "a.py"
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    cache = FilesystemFileAnalysisCache(tmp_path / "cache")

    class CountingAnalyzer:
        language = AlgorithmLanguage.PYTHON
        revision = "python-counting-v1"
        def __init__(self) -> None:
            self.calls = 0
        def analyze(self, document: SourceDocument):
            self.calls += 1
            return replace(
                PythonAlgorithmAnalyzer().analyze(document),
                analyzer_revision=self.revision,
            )

    first = CountingAnalyzer()
    AlgorithmScanner(
        inventory=RepositorySourceInventory(RepositorySourceTree(tmp_path)),
        analyzers=(first,),
        cache=cache,
        analyzer_implementation_digest="1" * 64,
    ).scan()
    assert first.calls == 1

    same_identity = CountingAnalyzer()
    AlgorithmScanner(
        inventory=RepositorySourceInventory(RepositorySourceTree(tmp_path)),
        analyzers=(same_identity,),
        cache=cache,
        analyzer_implementation_digest="1" * 64,
    ).scan()
    assert same_identity.calls == 0

    changed_identity = CountingAnalyzer()
    AlgorithmScanner(
        inventory=RepositorySourceInventory(RepositorySourceTree(tmp_path)),
        analyzers=(changed_identity,),
        cache=cache,
        analyzer_implementation_digest="2" * 64,
    ).scan()
    assert changed_identity.calls == 1



def test_implementation_text_digest_normalizes_only_line_endings(tmp_path: Path) -> None:
    from noetrium_platform.foundation.governance.api import (
        repository_source_scope_digest,
        repository_source_scope_text_digest,
    )

    target = tmp_path / "noetrium_platform" / "foundation" / "governance" / "algorithm" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"def f():\r\n    return 1\r\n")
    crlf = RepositorySourceTree(tmp_path).index()
    byte_crlf = repository_source_scope_digest(
        crlf,
        path_prefixes=("noetrium_platform/foundation/governance/algorithm",),
        suffixes=(".py",),
    )
    text_crlf = repository_source_scope_text_digest(
        crlf,
        path_prefixes=("noetrium_platform/foundation/governance/algorithm",),
        suffixes=(".py",),
    )

    target.write_bytes(b"def f():\n    return 1\n")
    lf = RepositorySourceTree(tmp_path).index()
    byte_lf = repository_source_scope_digest(
        lf,
        path_prefixes=("noetrium_platform/foundation/governance/algorithm",),
        suffixes=(".py",),
    )
    text_lf = repository_source_scope_text_digest(
        lf,
        path_prefixes=("noetrium_platform/foundation/governance/algorithm",),
        suffixes=(".py",),
    )
    assert byte_crlf != byte_lf
    assert text_crlf == text_lf

    target.write_bytes(b"def f():\n    return 2\n")
    changed = RepositorySourceTree(tmp_path).index()
    assert repository_source_scope_text_digest(
        changed,
        path_prefixes=("noetrium_platform/foundation/governance/algorithm",),
        suffixes=(".py",),
    ) != text_lf


def test_algorithm_governance_authority_hotpaths_remain_constant_time() -> None:
    import hashlib
    from noetrium_platform.foundation.governance.algorithm.api import AlgorithmLanguage, SourceDocument
    from noetrium_platform.foundation.governance.algorithm.runtime import PythonAlgorithmAnalyzer

    root = Path(__file__).resolve().parents[1]
    cases = (
        (
            "noetrium_platform/foundation/governance/algorithm/composition/default.py",
            "build_algorithm_governance",
            "O(1)",
            5,
        ),
        (
            "noetrium_platform/foundation/governance/algorithm/runtime/service.py",
            "AlgorithmGovernanceService.accept_baseline",
            "O(1)",
            5,
        ),
        (
            "noetrium_platform/foundation/governance/algorithm/api/contracts.py",
            "AlgorithmGovernanceApprovalSet.baseline_approval_for",
            "O(1)",
            1,
        ),
        (
            "noetrium_platform/foundation/governance/algorithm/api/contracts.py",
            "AlgorithmGovernanceApprovalSet.complexity_migration_for",
            "O(1)",
            1,
        ),
    )
    analyzer = PythonAlgorithmAnalyzer()
    for relative, qualified_name, expected_complexity, max_risk in cases:
        text = (root / relative).read_text(encoding="utf-8")
        document = SourceDocument(
            relative,
            AlgorithmLanguage.PYTHON,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            text,
        )
        symbol = next(
            row for row in analyzer.analyze(document).symbols
            if row.qualified_name == qualified_name
        )
        assert symbol.metrics.estimated_complexity == expected_complexity
        assert symbol.metrics.risk_score <= max_risk
