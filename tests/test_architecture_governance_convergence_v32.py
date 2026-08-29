from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_platform.governance.architecture.budget import (
    audit_architecture_complexity_budget,
    load_architecture_complexity_budget,
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


def _write_budget(root: Path, *, import_limit: int, justification: str) -> None:
    path = root / "research_platform" / "governance" / "architecture" / "ARCHITECTURE_BUDGET.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    baseline = {
        "top_level_systems": 17,
        "subsystems": 173,
        "contract_declarations": 129,
        "authorities": 190,
        "import_edges": 4749,
    }
    limits = dict(baseline)
    limits["import_edges"] = import_limit
    path.write_text(json.dumps({
        "schema_version": "architecture-complexity-budget.v1",
        "baseline_git_sha": "1" * 40,
        "baseline": baseline,
        "limits": limits,
        "migration_id": "source-index-v32" if import_limit > baseline["import_edges"] else "",
        "growth_justification": justification,
    }), encoding="utf-8")


def test_architecture_budget_requires_substantive_growth_justification(tmp_path: Path) -> None:
    _write_budget(tmp_path, import_limit=4750, justification="too short")
    with pytest.raises(ValueError, match="growth requires migration_id"):
        load_architecture_complexity_budget(tmp_path)


def test_architecture_budget_reports_import_edge_overrun(tmp_path: Path) -> None:
    _write_budget(
        tmp_path,
        import_limit=4750,
        justification="Canonical source-index migration adds explicit typed authority wiring only.",
    )
    _current, _budget, violations = audit_architecture_complexity_budget(
        tmp_path,
        import_edges=4751,
    )
    assert [(row.dimension, row.observed, row.limit) for row in violations] == [
        ("import_edges", 4751, 4750)
    ]


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
