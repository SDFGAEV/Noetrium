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


def _budget_document(*, baseline_git_sha: str = "1" * 40) -> dict[str, object]:
    return {
        "schema_version": "architecture-complexity-budget.v2",
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
        }],
    }


def _write_budget(root: Path, document: dict[str, object]) -> str:
    path = root / "research_platform" / "governance" / "architecture" / "ARCHITECTURE_BUDGET.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return architecture_budget_authority_digest(document)


def test_architecture_budget_rejects_nonhex_baseline_git_sha(tmp_path: Path) -> None:
    document = _budget_document(baseline_git_sha="z" * 40)
    authority = _write_budget(tmp_path, document)
    with pytest.raises(ValueError, match="lowercase 40-character Git SHA"):
        load_architecture_complexity_budget(tmp_path, expected_authority_sha256=authority)


def test_architecture_budget_rejects_uppercase_baseline_git_sha(tmp_path: Path) -> None:
    document = _budget_document(baseline_git_sha="A" * 40)
    authority = _write_budget(tmp_path, document)
    with pytest.raises(ValueError, match="lowercase 40-character Git SHA"):
        load_architecture_complexity_budget(tmp_path, expected_authority_sha256=authority)


def test_architecture_budget_rejects_forged_baseline_metrics(tmp_path: Path) -> None:
    document = _budget_document()
    reviewed_authority = architecture_budget_authority_digest(document)
    document["baseline"]["complexity"]["import_edges"] = 1
    _write_budget(tmp_path, document)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="review authority mismatch"):
        load_architecture_complexity_budget(
            tmp_path, expected_authority_sha256=reviewed_authority
        )


def test_architecture_budget_rejects_forged_migration_delta(tmp_path: Path) -> None:
    document = _budget_document()
    reviewed_authority = architecture_budget_authority_digest(document)
    document["migrations"][0]["delta"]["import_edges"] = 99
    _write_budget(tmp_path, document)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="review authority mismatch"):
        load_architecture_complexity_budget(
            tmp_path, expected_authority_sha256=reviewed_authority
        )


def test_architecture_budget_ledger_composes_reviewed_deltas() -> None:
    root = Path(__file__).resolve().parents[1]
    budget = load_architecture_complexity_budget(root)
    assert [item.delta.import_edges for item in budget.migrations] == [27, 2, 4, 22, 3, 14]
    assert sum(item.delta.import_edges for item in budget.migrations) == 72
    assert budget.limits.import_edges == 4821
    assert budget.limits.top_level_systems == 17


def test_architecture_budget_reports_import_edge_overrun(tmp_path: Path) -> None:
    document = _budget_document()
    authority = _write_budget(tmp_path, document)
    budget = load_architecture_complexity_budget(
        tmp_path, expected_authority_sha256=authority
    )
    assert budget.limits.import_edges == 4750
    _current, _ignored, violations = audit_architecture_complexity_budget(
        tmp_path,
        import_edges=4751,
        source_index=None,
        expected_authority_sha256=authority,
    )
    assert [(row.dimension, row.observed, row.limit) for row in violations] == [
        ("import_edges", 4751, 4750)
    ]


_GIT_PROJECTION_CACHE: dict[tuple[str, str], tuple[str, ArchitectureComplexity]] = {}


def _git_architecture_projection(
    repo_root: Path, git_sha: str
) -> tuple[str, ArchitectureComplexity]:
    key = (str(repo_root.resolve()), git_sha)
    cached = _GIT_PROJECTION_CACHE.get(key)
    if cached is not None:
        return cached
    archive = subprocess.run(
        ["git", "-C", str(repo_root), "archive", "--format=tar", git_sha],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    from research_platform.governance.architecture.source_profile import scan_architecture_source_profile
    from research_platform.governance.providers import RepositorySourceTree

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            bundle.extractall(target, filter="data")
        index = RepositorySourceTree(target).index()
        profile = scan_architecture_source_profile(target, source_index=index)
        catalog = json.loads(
            (target / "research_platform/governance/system_registry/catalog.json").read_text(
                encoding="utf-8"
            )
        )
        complexity = ArchitectureComplexity(
            top_level_systems=sum(row.get("parent") is None for row in catalog.values()),
            subsystems=sum(row.get("parent") is not None for row in catalog.values()),
            contract_declarations=sum(
                len(row.get("requires", [])) + len(row.get("provides", []))
                for row in catalog.values()
            ),
            authorities=sum(bool(row.get("authority")) for row in catalog.values()),
            import_edges=len(profile.import_edges),
        )
        result = (index.source_digest, complexity)
        _GIT_PROJECTION_CACHE[key] = result
        return result


def test_architecture_budget_baseline_is_independently_git_verifiable() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    budget = load_architecture_complexity_budget(repo_root)
    source_digest, complexity = _git_architecture_projection(
        repo_root, budget.baseline.git_sha
    )
    verify_architecture_baseline_authority(
        budget,
        git_sha=budget.baseline.git_sha,
        source_digest=source_digest,
        complexity=complexity,
    )


def test_architecture_budget_migration_sources_match_reviewed_deltas() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    budget = load_architecture_complexity_budget(repo_root)
    observed: dict[str, ArchitectureComplexity] = {}
    for migration in budget.migrations:
        _source_digest, complexity = _git_architecture_projection(
            repo_root, migration.source_git_sha
        )
        observed[migration.source_git_sha] = complexity
    verify_architecture_migration_sources(budget, observed)


def test_architecture_budget_migration_verifier_rejects_missing_source() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    budget = load_architecture_complexity_budget(repo_root)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="migration source unavailable"):
        verify_architecture_migration_sources(budget, {})


def test_release_quality_consumers_receive_one_frozen_source_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import research_platform.platform.composition.release_quality as quality_module
    from research_platform.governance.providers import RepositorySourceTree

    sentinel = object()
    seen: list[object] = []
    monkeypatch.setenv("RELEASE_QUALITY_SEQUENTIAL", "1")
    monkeypatch.setattr(RepositorySourceTree, "index", lambda _self: sentinel)

    def architecture(_root: str, index):
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
    quality_module.build_release_quality_evidence(tmp_path)
    assert seen == [sentinel, sentinel, sentinel, sentinel, sentinel]


def test_repository_source_cut_excludes_derived_release_evidence(tmp_path: Path) -> None:
    from research_platform.governance.providers import RepositorySourceTree

    source = tmp_path / "research_platform" / "x.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
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
