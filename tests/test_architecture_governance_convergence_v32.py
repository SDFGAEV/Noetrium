from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

import pytest

from research_platform.governance.architecture.budget import (
    ArchitectureBudgetProvenanceError,
    ArchitectureComplexity,
    architecture_budget_authority_digest,
    audit_architecture_complexity_budget,
    load_architecture_complexity_budget,
    verify_architecture_baseline_authority,
    verify_architecture_migration_sources,
)
from research_platform.governance.architecture.catalog_contract_invariants import (
    audit_catalog_contract_consistency,
)
from research_platform.governance.system_registry.api import system_catalog


def _leaf_source(descriptor, *, owns: str | None = None) -> str:
    package = descriptor.package_prefix
    return f'''from research_platform.platform.kernel.leaf_contract import SystemLeafContract
CONTRACT = SystemLeafContract(
    system_id={descriptor.identity.system_id!r},
    node={descriptor.identity.key!r},
    package_prefix={package!r},
    authority_id={descriptor.authority_id!r},
    owns={(owns if owns is not None else descriptor.owns)!r},
    must_not_own={descriptor.must_not_own!r},
    api_module={(package + ".api")!r},
    runtime_module={(package + ".runtime")!r},
    provider_module={(package + ".providers")!r},
    composition_module={(package + ".composition")!r},
)
'''


def test_catalog_contract_projection_accepts_exact_leaf(tmp_path: Path) -> None:
    descriptor = next(row for row in system_catalog() if row.identity.key == "execution/admission")
    boundary = tmp_path.joinpath(*descriptor.package_prefix.split("."), "api", "boundary.py")
    boundary.parent.mkdir(parents=True)
    boundary.write_text(_leaf_source(descriptor), encoding="utf-8")
    assert audit_catalog_contract_consistency(tmp_path) == []


def test_catalog_contract_projection_fails_closed_on_drift(tmp_path: Path) -> None:
    descriptor = next(row for row in system_catalog() if row.identity.key == "execution/admission")
    boundary = tmp_path.joinpath(*descriptor.package_prefix.split("."), "api", "boundary.py")
    boundary.parent.mkdir(parents=True)
    boundary.write_text(_leaf_source(descriptor, owns="drifted authority"), encoding="utf-8")
    rows = audit_catalog_contract_consistency(tmp_path)
    assert len(rows) == 1
    assert rows[0].invariant == "leaf_contract_catalog_drift"
    assert "execution/admission owns drift" in rows[0].detail


def _baseline_complexity(import_edges: int = 4749) -> dict[str, int]:
    return {
        "top_level_systems": 17,
        "subsystems": 173,
        "contract_declarations": 129,
        "authorities": 190,
        "import_edges": import_edges,
    }


def _budget_document(
    *,
    baseline_git_sha: str = "1" * 40,
    approval_status: str = "approved",
    projection: str = "a" * 64,
) -> dict[str, object]:
    applicability = (
        {"module_prefixes": ["research_platform.governance"], "import_projection_sha256": projection}
        if approval_status == "approved" else None
    )
    return {
        "schema_version": "architecture-complexity-budget.v3",
        "baseline": {
            "git_sha": baseline_git_sha,
            "source_digest": "2" * 64,
            "complexity": _baseline_complexity(),
        },
        "migrations": [{
            "migration_id": "test-reviewed-migration",
            "owner_role": "ROLE01",
            "source_git_sha": "3" * 40,
            "delta": {**_baseline_complexity(0), "top_level_systems": 0, "subsystems": 0,
                      "contract_declarations": 0, "authorities": 0, "import_edges": 1},
            "justification": "Reviewed test migration adds one explicit typed architecture dependency edge.",
            "approval": {
                "status": approval_status,
                "authority": "ROLE00",
                "evidence_ref": "SUPERVISOR_REVIEW_GATES.md#test-reviewed-migration",
            },
            "applicability": applicability,
        }],
    }


def _write_budget(root: Path, document: dict[str, object]) -> str:
    path = root / "research_platform" / "governance" / "architecture" / "ARCHITECTURE_BUDGET.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return architecture_budget_authority_digest(document)


def test_architecture_budget_rejects_nonhex_baseline_git_sha(tmp_path: Path) -> None:
    authority = _write_budget(tmp_path, _budget_document(baseline_git_sha="z" * 40))
    with pytest.raises(ValueError, match="lowercase 40-character Git SHA"):
        load_architecture_complexity_budget(tmp_path, expected_authority_sha256=authority)


def test_architecture_budget_rejects_uppercase_baseline_git_sha(tmp_path: Path) -> None:
    authority = _write_budget(tmp_path, _budget_document(baseline_git_sha="A" * 40))
    with pytest.raises(ValueError, match="lowercase 40-character Git SHA"):
        load_architecture_complexity_budget(tmp_path, expected_authority_sha256=authority)


def test_architecture_budget_document_digest_detects_isolated_tamper(tmp_path: Path) -> None:
    document = _budget_document()
    reviewed_digest = architecture_budget_authority_digest(document)
    document["baseline"]["complexity"]["import_edges"] = 1
    _write_budget(tmp_path, document)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="document digest mismatch"):
        load_architecture_complexity_budget(tmp_path, expected_authority_sha256=reviewed_digest)


def test_proposed_migration_never_raises_effective_limit(tmp_path: Path) -> None:
    _write_budget(tmp_path, _budget_document(approval_status="proposed"))
    _current, budget, violations = audit_architecture_complexity_budget(
        tmp_path, import_edges=4750, import_edge_pairs=(), verify_provenance=False
    )
    assert budget is not None
    assert budget.limits.import_edges == 4749
    assert budget.applicable_migration_ids == ()
    assert [(row.observed, row.limit) for row in violations] == [(4750, 4749)]


def test_approved_migration_requires_exact_projection_match(tmp_path: Path) -> None:
    from research_platform.governance.architecture.budget import import_projection_digest

    pairs = (("research_platform.governance.a", "research_platform.platform.b"),)
    projection = import_projection_digest(pairs, ("research_platform.governance",))
    _write_budget(tmp_path, _budget_document(projection=projection))
    _current, budget, violations = audit_architecture_complexity_budget(
        tmp_path, import_edges=4750, import_edge_pairs=pairs, verify_provenance=False
    )
    assert budget is not None
    assert budget.limits.import_edges == 4750
    assert budget.applicable_migration_ids == ("test-reviewed-migration",)
    assert violations == ()
    _current, budget, violations = audit_architecture_complexity_budget(
        tmp_path,
        import_edges=4750,
        import_edge_pairs=(("research_platform.scope.x", "research_platform.platform.y"),),
        verify_provenance=False,
    )
    assert budget is not None
    assert budget.limits.import_edges == 4749
    assert [(row.observed, row.limit) for row in violations] == [(4750, 4749)]


def test_formal_budget_audit_invokes_baseline_and_approved_source_verifier(tmp_path: Path) -> None:
    from research_platform.governance.architecture.budget import (
        ArchitectureMigrationObservation,
        import_projection_digest,
    )
    from research_platform.governance.providers import RepositorySourceIndex, RepositorySourceTree

    pairs = (("research_platform.governance.a", "research_platform.platform.b"),)
    projection = import_projection_digest(pairs, ("research_platform.governance",))
    document = _budget_document(projection=projection)
    _write_budget(tmp_path, document)
    marker = tmp_path / "research_platform" / "governance" / "architecture" / "report.py"
    marker.write_text("VALUE = 1\n", encoding="utf-8")
    catalog = tmp_path / "research_platform" / "governance" / "system_registry" / "catalog.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text("{}", encoding="utf-8")
    snapshot = RepositorySourceTree(tmp_path).snapshot()
    index = RepositorySourceIndex(snapshot, source_authority="git", source_revision="4" * 40)
    calls: list[tuple[str, tuple[str, ...]]] = []

    def resolve(sha: str, prefixes: tuple[str, ...]):
        calls.append((sha, prefixes))
        if sha == "1" * 40:
            return "2" * 64, ArchitectureMigrationObservation(
                complexity=ArchitectureComplexity(**_baseline_complexity()),
                import_projection_sha256=None,
            )
        return "5" * 64, ArchitectureMigrationObservation(
            complexity=ArchitectureComplexity(**_baseline_complexity(4750)),
            import_projection_sha256=projection,
        )

    _current, budget, violations = audit_architecture_complexity_budget(
        tmp_path,
        import_edges=4750,
        import_edge_pairs=pairs,
        source_index=index,
        verify_provenance=True,
        historical_observation_resolver=resolve,
    )
    assert violations == ()
    assert budget is not None and budget.limits.import_edges == 4750
    assert calls == [("1" * 40, ()), ("3" * 40, ("research_platform.governance",))]


def test_current_role01_budget_cannot_borrow_other_role_allowances() -> None:
    from research_platform.governance.architecture.source_profile import scan_architecture_source_profile
    from research_platform.governance.providers import RepositorySourceTree

    root = Path(__file__).resolve().parents[1]
    index = RepositorySourceTree(root).index()
    profile = scan_architecture_source_profile(root, source_index=index)
    pairs = tuple((edge.source_module, edge.target_module) for edge in profile.import_edges)
    for observed in (4777, 4800, 4821):
        _current, budget, violations = audit_architecture_complexity_budget(
            root,
            import_edges=observed,
            import_edge_pairs=pairs,
            source_index=index,
            verify_provenance=False,
        )
        assert budget is not None
        assert budget.limits.import_edges == 4776
        assert budget.applicable_migration_ids == ("role01-shared-source-index-v1",)
        assert [(row.observed, row.limit) for row in violations] == [(observed, 4776)]


def _test_git_executable() -> str:
    import os
    import shutil

    configured = os.environ.get("RESEARCH_PLATFORM_GIT_EXECUTABLE", "").strip()
    executable = configured or shutil.which("git")
    if not executable:
        pytest.skip("Git executable is required for immutable source authority test")
    return executable


def test_git_source_cut_is_pinned_against_worktree_and_head_changes(tmp_path: Path) -> None:
    from research_platform.governance.providers import GitRepositorySourceTree

    git = _test_git_executable()
    def run(*args: str) -> None:
        subprocess.run([git, "-C", str(tmp_path), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run("init")
    run("config", "user.email", "role01-test@example.invalid")
    run("config", "user.name", "ROLE01 Test")
    source = tmp_path / "research_platform" / "x.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"VALUE = 1\n")
    run("add", ".")
    run("commit", "-m", "baseline")
    provider = GitRepositorySourceTree(tmp_path, git_executable=git)
    pinned_revision = provider.revision
    source.write_bytes(b"VALUE = 2\n")
    (source.parent / "new.py").write_bytes(b"NEW = 1\n")
    first = provider.index()
    assert first.source_revision == pinned_revision
    assert first.text("research_platform/x.py") == "VALUE = 1\n"
    assert tuple(blob.relative_path for blob in first.documents(suffixes={".py"})) == ("research_platform/x.py",)
    run("add", ".")
    run("commit", "-m", "advance-head")
    second = provider.index()
    assert second.source_revision == pinned_revision
    assert second.source_digest == first.source_digest
    assert second.text("research_platform/x.py") == "VALUE = 1\n"


def test_release_quality_consumers_receive_one_frozen_source_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import research_platform.platform.composition.release_quality as quality_module

    sentinel = object()
    seen: list[object] = []
    monkeypatch.setenv("RELEASE_QUALITY_SEQUENTIAL", "1")

    def architecture(_root: str, index, _git_executable=None):
        seen.append(index); return "a" * 64, True
    def guards(_root: str, index):
        seen.append(index); return 0, 0
    def algorithm(_root: str, index):
        seen.append(index); return "b" * 64, True, 0
    def concurrency(_root: str, index):
        seen.append(index); return "c" * 64, True, 0
    def performance(_root: str, index):
        seen.append(index); return "d" * 64, True, 0

    monkeypatch.setattr(quality_module, "_architecture_lane", architecture)
    monkeypatch.setattr(quality_module, "_quality_guard_lane", guards)
    monkeypatch.setattr(quality_module, "_algorithm_lane", algorithm)
    monkeypatch.setattr(quality_module, "_concurrency_lane", concurrency)
    monkeypatch.setattr(quality_module, "_performance_lane", performance)
    quality_module.build_release_quality_evidence(tmp_path, source_index=sentinel)
    assert seen == [sentinel, sentinel, sentinel, sentinel, sentinel]


def test_repository_source_cut_excludes_derived_release_evidence(tmp_path: Path) -> None:
    from research_platform.governance.providers import RepositorySourceTree

    source = tmp_path / "research_platform" / "x.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"VALUE = 1\n")
    before = RepositorySourceTree(tmp_path).index()
    (tmp_path / "RELEASE_EVIDENCE.json").write_text('{"derived": true}\n', encoding="utf-8")
    after = RepositorySourceTree(tmp_path).index()

    assert before.source_digest == after.source_digest
    assert [row.relative_path for row in after.documents(suffixes={".json"})] == []


def test_no_degradation_standalone_fails_closed_on_python_syntax(tmp_path: Path) -> None:
    from research_platform.governance.api import RepositorySourceFailureKind, RepositorySourceIncompleteError
    from research_platform.governance.quality import scan_no_degradation

    source = tmp_path / "research_platform" / "broken.py"
    source.parent.mkdir(parents=True)
    source.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(RepositorySourceIncompleteError) as raised:
        scan_no_degradation(tmp_path)
    assert raised.value.failures[0].kind is RepositorySourceFailureKind.PYTHON_PARSE


def test_no_degradation_standalone_fails_closed_on_malformed_json(tmp_path: Path) -> None:
    from research_platform.governance.api import RepositorySourceFailureKind, RepositorySourceIncompleteError
    from research_platform.governance.quality import scan_no_degradation

    config = tmp_path / "configs" / "broken.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"enabled": ', encoding="utf-8")
    with pytest.raises(RepositorySourceIncompleteError) as raised:
        scan_no_degradation(tmp_path)
    assert raised.value.failures[0].kind is RepositorySourceFailureKind.CONFIG_PARSE


def test_source_invariant_paths_use_canonical_posix_identity(tmp_path: Path) -> None:
    from research_platform.governance.architecture.source_scan import violation

    source = tmp_path / "research_platform" / "execution" / "admission" / "api" / "boundary.py"
    row = violation(tmp_path, source, "test", 1, "detail")
    assert row.path == "research_platform/execution/admission/api/boundary.py"
