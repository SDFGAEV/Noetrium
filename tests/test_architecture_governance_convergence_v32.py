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
    ArchitectureMigrationApproval,
    ArchitectureMigrationApprovalSet,
    ArchitectureMigrationObservation,
    audit_architecture_complexity_budget,
    import_projection_digest,
    load_architecture_complexity_budget,
    load_architecture_migration_approval_set,
    source_scope_digest,
)
from research_platform.governance.architecture.catalog_contract_invariants import (
    audit_catalog_contract_consistency,
)
from research_platform.governance.system_registry.api import system_catalog
from research_platform.governance.architecture.system_topology_invariants import audit_system_topology_completeness


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
        "subsystems": 174,
        "contract_declarations": 142,
        "authorities": 191,
        "import_edges": import_edges,
    }


def _budget_document(*, projection: str | None = None) -> dict[str, object]:
    return {
        "schema_version": "architecture-complexity-budget.v3",
        "baseline": {
            "git_sha": "1" * 40,
            "source_digest": "2" * 64,
            "complexity": _baseline_complexity(),
        },
        "migrations": [{
            "migration_id": "test-reviewed-migration",
            "owner_role": "ROLE01",
            "delta": {"top_level_systems":0,"subsystems":0,"contract_declarations":0,"authorities":0,"import_edges":1},
            "justification": "Test proposal adds one explicit typed architecture dependency for external approval validation.",
            "applicability": None if projection is None else {
                "module_prefixes": ["research_platform.governance"],
                "import_projection_sha256": projection,
            },
        }],
    }


def _write_budget(root: Path, document: dict[str, object]) -> None:
    path = root / "research_platform/governance/architecture/ARCHITECTURE_BUDGET.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _approval_record(*, source_digest: str = "b" * 64, delta: int = 1) -> dict[str, object]:
    import hashlib
    record: dict[str, object] = {
        "schema": "supervisor.architecture-migration-approval.v1",
        "migration_id": "test-reviewed-migration",
        "dimension": "import_edges",
        "source_sha": "3" * 40,
        "source_digest": source_digest,
        "delta": delta,
        "decision": "approved",
        "authority": "ROLE00",
        "scope": "architecture-import-edge-migration-only",
        "review_state": "READY_FOR_REVIEW",
        "review_evidence_refs": ["state/SUPERVISOR_REVIEW_GATES.md#test"],
        "issued_at": "2026-08-30T10:34:00+08:00",
        "note": "Synthetic external approval used only to verify the typed independent approval trust boundary.",
    }
    payload=json.dumps(record,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode()
    record["approval_record_sha256"]=hashlib.sha256(payload).hexdigest()
    return record


def _typed_approval_set(*, source_digest: str = "b" * 64, delta: int = 1) -> ArchitectureMigrationApprovalSet:
    row=_approval_record(source_digest=source_digest, delta=delta)
    approval=ArchitectureMigrationApproval(
        schema_version=str(row["schema"]), migration_id=str(row["migration_id"]),
        source_git_sha=str(row["source_sha"]), source_digest=str(row["source_digest"]),
        complexity_delta=ArchitectureComplexity(0, 0, 0, 0, int(row["delta"])),
        decision="approved", authority="ROLE00", scope=str(row["scope"]),
        review_state=str(row["review_state"]),
        review_evidence_refs=tuple(row["review_evidence_refs"]), issued_at=str(row["issued_at"]),
        note=str(row["note"]), approval_record_sha256=str(row["approval_record_sha256"]),
    )
    return ArchitectureMigrationApprovalSet(
        schema_version="supervisor.architecture-migration-approval-set.v1",
        authority="ROLE00", baseline_git_sha="1"*40, approvals=(approval,),
        default_decision="not_approved", rule="test external approval rule",
    )


def _typed_v2_approval_set(delta: ArchitectureComplexity) -> ArchitectureMigrationApprovalSet:
    import hashlib
    record = {
        "schema": "supervisor.architecture-migration-approval.v2",
        "migration_id": "test-reviewed-migration",
        "complexity_delta": {field: getattr(delta, field) for field in (
            "top_level_systems", "subsystems", "contract_declarations", "authorities", "import_edges"
        )},
        "source_sha": "3" * 40, "source_digest": "b" * 64,
        "decision": "approved", "authority": "ROLE00",
        "scope": "architecture-complexity-migration-only",
        "review_state": "READY_FOR_REVIEW",
        "review_evidence_refs": ["state/SUPERVISOR_REVIEW_GATES.md#test-v2"],
        "issued_at": "2026-08-30T16:08:00+08:00",
        "note": "Synthetic full-complexity approval for multidimensional migration tests.",
    }
    payload=json.dumps(record,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode()
    record["approval_record_sha256"]=hashlib.sha256(payload).hexdigest()
    approval=ArchitectureMigrationApproval(
        schema_version=str(record["schema"]), migration_id=str(record["migration_id"]),
        source_git_sha=str(record["source_sha"]), source_digest=str(record["source_digest"]),
        complexity_delta=delta, decision="approved", authority="ROLE00",
        scope=str(record["scope"]), review_state=str(record["review_state"]),
        review_evidence_refs=tuple(record["review_evidence_refs"]), issued_at=str(record["issued_at"]),
        note=str(record["note"]), approval_record_sha256=str(record["approval_record_sha256"]),
    )
    return ArchitectureMigrationApprovalSet(
        schema_version="supervisor.architecture-migration-approval-set.v1", authority="ROLE00",
        baseline_git_sha="1"*40, approvals=(approval,), default_decision="not_approved",
        rule="test full-complexity external approval rule",
    )

def _synthetic_git_index(root: Path):
    from research_platform.governance.providers import RepositorySourceIndex, RepositorySourceTree
    marker=root/"research_platform/governance/architecture/report.py"
    marker.parent.mkdir(parents=True, exist_ok=True); marker.write_text("VALUE=1\n",encoding="utf-8")
    owner=root/"research_platform/governance/x.py"; owner.write_text("VALUE=1\n",encoding="utf-8")
    fs=RepositorySourceTree(root).snapshot()
    return RepositorySourceIndex(fs, source_authority="git", source_revision="4"*40)


def test_architecture_budget_rejects_nonhex_baseline_git_sha(tmp_path: Path) -> None:
    doc=_budget_document(); doc["baseline"]["git_sha"]="z"*40; _write_budget(tmp_path,doc)
    with pytest.raises(ValueError, match="lowercase 40-character Git SHA"):
        load_architecture_complexity_budget(tmp_path)


def test_worker_budget_cannot_self_assert_role00_approval(tmp_path: Path) -> None:
    doc=_budget_document(); doc["migrations"][0]["approval"]={"status":"approved","authority":"ROLE00","evidence_ref":"fake"}
    _write_budget(tmp_path,doc)
    with pytest.raises(ValueError, match="unexpected fields"):
        load_architecture_complexity_budget(tmp_path)


def test_external_approval_set_requires_exact_file_digest(tmp_path: Path) -> None:
    import hashlib
    doc={"schema":"supervisor.architecture-migration-approval-set.v1","authority":"ROLE00","baseline_sha":"1"*40,
         "approvals":[_approval_record()],"default_decision":"not_approved","rule":"exact typed external approval only"}
    path=tmp_path/"approvals.json"; raw=(json.dumps(doc,indent=2)+"\n").encode(); path.write_bytes(raw)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="approval set digest mismatch"):
        load_architecture_migration_approval_set(path, expected_sha256="0"*64)
    loaded=load_architecture_migration_approval_set(path, expected_sha256=hashlib.sha256(raw).hexdigest())
    assert loaded.authority == "ROLE00" and loaded.approvals[0].approved


def test_external_approval_record_digest_is_verified(tmp_path: Path) -> None:
    import hashlib
    row=_approval_record(); row["delta"]=99
    doc={"schema":"supervisor.architecture-migration-approval-set.v1","authority":"ROLE00","baseline_sha":"1"*40,
         "approvals":[row],"default_decision":"not_approved","rule":"exact typed external approval only"}
    path=tmp_path/"approvals.json"; raw=json.dumps(doc).encode(); path.write_bytes(raw)
    with pytest.raises(ArchitectureBudgetProvenanceError, match="approval record digest mismatch"):
        load_architecture_migration_approval_set(path, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_external_approval_applies_only_to_exact_owner_source_scope(tmp_path: Path) -> None:
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    _write_budget(tmp_path,_budget_document(projection=projection))
    index=_synthetic_git_index(tmp_path)
    owner_digest=source_scope_digest(index,("research_platform.governance",))
    calls=[]
    def resolve(sha: str, prefixes: tuple[str,...]):
        calls.append((sha,prefixes))
        if sha == "1"*40:
            return "2"*64, ArchitectureMigrationObservation(ArchitectureComplexity(**_baseline_complexity()),None,None)
        return "b"*64, ArchitectureMigrationObservation(
            ArchitectureComplexity(**_baseline_complexity(4750)), projection, owner_digest
        )
    _current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_approval_set(),historical_observation_resolver=resolve,verify_provenance=True)
    assert violations == () and budget is not None and budget.limits.import_edges == 4750
    assert budget.applicable_migration_ids == ("test-reviewed-migration",)
    assert calls == [("1"*40,()),("3"*40,("research_platform.governance",))]


def test_mismatched_external_source_digest_contributes_zero_headroom(tmp_path: Path) -> None:
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    _write_budget(tmp_path,_budget_document(projection=projection)); index=_synthetic_git_index(tmp_path)
    owner_digest=source_scope_digest(index,("research_platform.governance",))
    def resolve(sha: str, prefixes: tuple[str,...]):
        if sha == "1"*40:
            return "2"*64, ArchitectureMigrationObservation(ArchitectureComplexity(**_baseline_complexity()),None,None)
        return "b"*64, ArchitectureMigrationObservation(ArchitectureComplexity(**_baseline_complexity(4750)),projection,owner_digest)
    _current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_approval_set(source_digest="c"*64),historical_observation_resolver=resolve,verify_provenance=True)
    assert budget is not None and budget.limits.import_edges == 4749
    assert [(v.observed,v.limit) for v in violations] == [(4750,4749)]


def _multidim_budget_document(projection: str) -> dict[str, object]:
    return {
        "schema_version": "architecture-complexity-budget.v3",
        "baseline": {
            "git_sha": "1" * 40, "source_digest": "2" * 64,
            "complexity": {"top_level_systems":17,"subsystems":173,"contract_declarations":141,"authorities":190,"import_edges":4749},
        },
        "migrations": [{
            "migration_id": "test-reviewed-migration", "owner_role": "ROLE01",
            "delta": {"top_level_systems":0,"subsystems":1,"contract_declarations":1,"authorities":1,"import_edges":1},
            "justification": "Synthetic multidimensional migration proves complete external complexity authority binding.",
            "applicability": {
                "module_prefixes": ["research_platform.governance"],
                "import_projection_sha256": projection,
            },
        }],
    }

def _multidim_resolver(projection: str, owner_digest: str):
    def resolve(sha: str, prefixes: tuple[str, ...]):
        if sha == "1" * 40:
            return "2" * 64, ArchitectureMigrationObservation(ArchitectureComplexity(17,173,141,190,4749),None,None)
        return "b" * 64, ArchitectureMigrationObservation(ArchitectureComplexity(17,174,142,191,4750),projection,owner_digest)
    return resolve

def test_v2_approval_file_decodes_complete_complexity_delta(tmp_path: Path) -> None:
    import hashlib
    delta={"top_level_systems":0,"subsystems":1,"contract_declarations":1,"authorities":1,"import_edges":1}
    row={
        "schema":"supervisor.architecture-migration-approval.v2",
        "migration_id":"test-reviewed-migration", "complexity_delta":delta,
        "source_sha":"3"*40, "source_digest":"b"*64, "decision":"approved",
        "authority":"ROLE00", "scope":"architecture-complexity-migration-only",
        "review_state":"READY_FOR_REVIEW",
        "review_evidence_refs":["state/SUPERVISOR_REVIEW_GATES.md#test-v2-file"],
        "issued_at":"2026-08-30T16:08:00+08:00",
        "note":"Synthetic file-backed multidimensional approval decode test.",
    }
    payload=json.dumps(row,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode()
    row["approval_record_sha256"]=hashlib.sha256(payload).hexdigest()
    doc={"schema":"supervisor.architecture-migration-approval-set.v1","authority":"ROLE00",
         "baseline_sha":"1"*40,"approvals":[row],"default_decision":"not_approved",
         "rule":"full complexity records must bind every non-zero dimension"}
    raw=(json.dumps(doc,indent=2)+"\n").encode(); path=tmp_path/"approvals-v2.json"; path.write_bytes(raw)
    loaded=load_architecture_migration_approval_set(path,expected_sha256=hashlib.sha256(raw).hexdigest())
    assert loaded.approvals[0].complexity_delta == ArchitectureComplexity(0,1,1,1,1)

def _patch_multidim_current(monkeypatch) -> None:
    import research_platform.governance.architecture.budget as budget_module

    monkeypatch.setattr(
        budget_module,
        "current_architecture_complexity",
        lambda *, import_edges: ArchitectureComplexity(17, 174, 142, 191, import_edges),
    )


def test_v1_import_approval_cannot_authorize_multidimensional_migration(tmp_path: Path, monkeypatch) -> None:
    _patch_multidim_current(monkeypatch)
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    _write_budget(tmp_path,_multidim_budget_document(projection)); index=_synthetic_git_index(tmp_path)
    owner=source_scope_digest(index,("research_platform.governance",))
    _current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_approval_set(),historical_observation_resolver=_multidim_resolver(projection,owner),
        verify_provenance=True)
    assert budget is not None and budget.applicable_migration_ids == ()
    assert {v.dimension for v in violations} == {"subsystems","contract_declarations","authorities","import_edges"}

def test_v2_full_complexity_approval_authorizes_exact_multidimensional_migration(tmp_path: Path, monkeypatch) -> None:
    _patch_multidim_current(monkeypatch)
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    _write_budget(tmp_path,_multidim_budget_document(projection)); index=_synthetic_git_index(tmp_path)
    owner=source_scope_digest(index,("research_platform.governance",))
    delta=ArchitectureComplexity(0,1,1,1,1)
    _current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_v2_approval_set(delta),historical_observation_resolver=_multidim_resolver(projection,owner),
        verify_provenance=True)
    assert violations == () and budget is not None
    assert budget.applicable_migration_ids == ("test-reviewed-migration",)
    assert budget.limits == ArchitectureComplexity(17,174,142,191,4750)

def test_v2_mismatched_complexity_delta_contributes_zero_headroom(tmp_path: Path, monkeypatch) -> None:
    _patch_multidim_current(monkeypatch)
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    _write_budget(tmp_path,_multidim_budget_document(projection)); index=_synthetic_git_index(tmp_path)
    owner=source_scope_digest(index,("research_platform.governance",))
    wrong=ArchitectureComplexity(0,1,1,0,1)
    _current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_v2_approval_set(wrong),historical_observation_resolver=_multidim_resolver(projection,owner),
        verify_provenance=True)
    assert budget is not None and budget.applicable_migration_ids == ()
    assert {v.dimension for v in violations} == {"subsystems","contract_declarations","authorities","import_edges"}

def test_v2_approval_record_requires_whole_migration_scope(tmp_path: Path) -> None:
    import hashlib
    delta=ArchitectureComplexity(0,1,1,1,1)
    approval_set=_typed_v2_approval_set(delta)
    approval=approval_set.approvals[0]
    assert approval.scope == "architecture-complexity-migration-only"
    assert approval.complexity_delta == delta

def test_current_role01_has_no_self_granted_headroom() -> None:
    from research_platform.governance.architecture.source_profile import scan_architecture_source_profile
    from research_platform.governance.providers import RepositorySourceTree
    root=Path(__file__).resolve().parents[1]; index=RepositorySourceTree(root).index()
    profile=scan_architecture_source_profile(root,source_index=index)
    pairs=tuple((e.source_module,e.target_module) for e in profile.import_edges)
    _current,budget,violations=audit_architecture_complexity_budget(
        root,import_edges=len(profile.import_edges),import_edge_pairs=pairs,source_index=index,verify_provenance=False)
    assert budget is not None and budget.limits.import_edges == 4749
    assert budget.applicable_migration_ids == ()
    assert any(v.dimension == "import_edges" and v.limit == 4749 for v in violations)


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

def test_role04_historical_and_npe_architecture_allowances_are_preserved() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = {row.migration_id: row for row in load_architecture_complexity_budget(root).migrations}
    historical = rows["role04-participant-model-v1"]
    current = rows["role04-npe-participant-model-248d67c"]
    assert historical.delta.import_edges == 41
    assert historical.module_prefixes == ("research_platform.participant", "research_platform.model")
    assert historical.import_projection_sha256 == "dcd7c1e5a32e7a57e466c8f0a1a1b866bde249f7f6cc57d1af1362fff38ae25e"
    assert current.delta.import_edges == 60
    assert current.module_prefixes == ("research_platform.participant", "research_platform.model")
    assert current.import_projection_sha256 == "258324fc514e5aa069f069d5d9282f0433c35a20bbbdd3da8782530cef40b643"

def test_role05_historical_and_final_quality_architecture_allowances_are_preserved() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = {row.migration_id: row for row in load_architecture_complexity_budget(root).migrations}
    historical = rows["role05-environment-evidence-v1"]
    current = rows["role05-final-quality-environment-evidence-2e20464"]
    prefixes = ("research_platform.environment", "research_platform.data", "research_platform.artifact", "research_platform.observability")
    assert historical.delta.import_edges == 2
    assert historical.module_prefixes == prefixes
    assert historical.import_projection_sha256 == "6f9fdf4f5d64703e1be10d2707b49109e365bb7343cd5118a05e73a6e3a5e62b"
    assert current.delta.import_edges == 19
    assert current.module_prefixes == prefixes
    assert current.import_projection_sha256 == "cee2b53c07b2465a13fc40599e27dd22fa950989fa55eb0fccad98881904d7c2"


def test_current_downstream_proposals_have_exact_applicability_without_self_approval() -> None:
    root = Path(__file__).resolve().parents[1]
    budget = load_architecture_complexity_budget(root)
    expected = {
        "ROLE02": (8, ("research_platform.runtime", "research_platform.resource", "research_platform.reliability"), "e48da451b73527f4e5283fdbf3424c171e9c15d8f48eeaa47b6ec5dbf886e5c8"),
        "ROLE06": (20, ("research_platform.operator", "research_platform.api"), "9810e526f81fdc118f966628b6eec243219304799060fe4b4c1ec72b7843bfa2"),
    }
    for role, (delta, prefixes, projection) in expected.items():
        migration = next(row for row in budget.migrations if row.owner_role == role)
        assert migration.delta.import_edges == delta
        assert migration.module_prefixes == prefixes
        assert migration.import_projection_sha256 == projection


def test_portfolio_catalog_declares_canonical_manifest_dependencies() -> None:
    descriptor = next(row for row in system_catalog() if row.identity.key == "portfolio")
    assert descriptor.requires == ("platform", "scope")


def test_operator_catalog_declares_run_control_dependencies() -> None:
    descriptor = next(row for row in system_catalog() if row.identity.key == "operator")
    assert descriptor.requires == (
        "environment",
        "execution",
        "experimentation",
        "governance",
        "model",
        "observability",
        "platform",
        "portfolio",
        "reliability",
        "resource",
        "scope",
    )


def test_run_control_catalog_registration_matches_exact_role03_boundary() -> None:
    descriptor=next(row for row in system_catalog() if row.identity.key=="experimentation/run/control")
    assert descriptor.authority_id=="run_control"
    assert descriptor.owns=="durable generic run lifecycle control authority and fenced control generations"
    assert descriptor.must_not_own=="operator product intents, server supervision internals or duplicate run manifest/checkpoint truth"
    assert descriptor.requires==("execution","execution/operation","experimentation/checkpoint","experimentation/run","experimentation/run/identity","experimentation/run/lifecycle","experimentation/run/manifest","platform")
    assert descriptor.provides==("run.control",)

def test_run_control_standard_shape_is_registered(tmp_path: Path) -> None:
    leaf=tmp_path/'research_platform/experimentation/run/control'
    for plane in ("api","runtime","providers","composition"):
        p=leaf/plane; p.mkdir(parents=True); (p/'__init__.py').write_text('',encoding='utf-8')
    (leaf/'__init__.py').write_text('',encoding='utf-8')
    assert audit_system_topology_completeness(tmp_path)==[]

def test_role01_historical_and_current_architecture_allowances_are_preserved() -> None:
    rows={row.migration_id:row for row in load_architecture_complexity_budget(Path(__file__).resolve().parents[1]).migrations}
    historical=rows["role01-shared-source-index-v1"]
    provenance=rows["role01-governance-provenance-9ba9f6e"]
    public_seam=rows["role01-governance-public-seam-b96087e"]
    current=rows["role01-platform-semantic-convergence-v1"]
    contraction=rows["role01-semantic-catalog-contraction-v1"]
    assert (historical.delta.subsystems,historical.delta.contract_declarations,historical.delta.authorities,historical.delta.import_edges)==(1,12,1,31)
    assert historical.import_projection_sha256=="f1f77c3e85117adc449c56dd807bdd46b3f3d1b4412f677bcb40b8b2548f0699"
    assert (provenance.delta.subsystems,provenance.delta.contract_declarations,provenance.delta.authorities,provenance.delta.import_edges)==(1,12,1,56)
    assert provenance.import_projection_sha256=="49e0ee63db04e96e738645ce5f00ff514bb9172c40e2d6e8f9d5312f0c52917e"
    assert (public_seam.delta.subsystems,public_seam.delta.contract_declarations,public_seam.delta.authorities,public_seam.delta.import_edges)==(1,13,1,54)
    assert public_seam.import_projection_sha256=="1e0c06fd1777a81e2c573891c1c39f62627c37ca138e2683d0566889dc64f714"
    assert (current.delta.subsystems,current.delta.contract_declarations,current.delta.authorities,current.delta.import_edges)==(1,13,1,59)
    assert current.module_prefixes==("research_platform.platform","research_platform.governance","research_platform.scope","research_platform.portfolio")
    assert current.import_projection_sha256=="fd225e4d33b57a9f4b52495941b69d89f33cb333ddcc031ab87a983b8c1f6c98"
    assert (contraction.delta.subsystems,contraction.delta.contract_declarations,contraction.delta.authorities,contraction.delta.import_edges)==(-1,13,-1,39)
    assert contraction.module_prefixes==current.module_prefixes
    assert contraction.import_projection_sha256=="59de5bba61ab0b83d094b2aab97e952b79be8ece954e3fa1ef89a33267d64a48"

def test_role03_historical_and_npe_architecture_allowances_are_preserved() -> None:
    rows={row.migration_id:row for row in load_architecture_complexity_budget(Path(__file__).resolve().parents[1]).migrations}
    historical=rows["role03-run-control-693c4814d590"]
    current=rows["role03-npe-run-control-2722fe1"]
    assert historical.delta.import_edges==38
    assert historical.import_projection_sha256=="aec91782b6e3cac009ea998614aa86594ed0fb2cfc917c8c49f7b81dedad8aa3"
    assert current.delta.import_edges==52
    assert current.module_prefixes==("research_platform.execution","research_platform.experimentation","research_platform.scientific")
    assert current.import_projection_sha256=="e69dbebfd7126e1c55c3c42c79073428f86ba547febc20630e0497a763aed87c"



def _semantic_boundary_fixture(tmp_path: Path) -> Path:
    catalog = {
        "demo": {
            "package_prefix": "research_platform.demo",
            "requires": [], "provides": ["demo.aggregate"], "components": [],
        },
        "demo/declarative": {
            "package_prefix": "research_platform.demo.declarative",
            "requires": [], "provides": ["demo.read"], "components": [],
        },
        "demo/generic": {
            "package_prefix": "research_platform.demo.generic",
            "requires": [], "provides": [], "components": [],
        },
        "demo/implemented": {
            "package_prefix": "research_platform.demo.implemented",
            "requires": [], "provides": [], "components": [],
        },
    }
    catalog_path = tmp_path / "research_platform/governance/system_registry/catalog.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    generic = tmp_path / "research_platform/demo/generic/runtime/owner.py"
    generic.parent.mkdir(parents=True, exist_ok=True)
    generic.write_text(
        "from research_platform.platform.kernel.leaf_contract import BoundSystemLeafRuntime, FileLeafStateStore\n"
        "def runtime(handler, state_path=None) -> BoundSystemLeafRuntime:\n    return handler(state_path)\n",
        encoding="utf-8",
    )
    declarative = tmp_path / "research_platform/demo/declarative/api/boundary.py"
    declarative.parent.mkdir(parents=True, exist_ok=True)
    declarative.write_text("# declarative catalog facet only\n", encoding="utf-8")
    implemented = tmp_path / "research_platform/demo/implemented/providers/sqlite.py"
    implemented.parent.mkdir(parents=True, exist_ok=True)
    implemented.write_text("class SQLiteDemoStore:\n    pass\n", encoding="utf-8")
    return tmp_path


def test_semantic_boundary_inventory_distinguishes_synthetic_shells_from_domain_authority(tmp_path: Path) -> None:
    from research_platform.governance.architecture import classify_semantic_boundaries
    from research_platform.governance.architecture.api import SemanticBoundaryClassification

    rows = {row.node: row for row in classify_semantic_boundaries(_semantic_boundary_fixture(tmp_path))}
    assert rows["demo"].classification is SemanticBoundaryClassification.DECLARATIVE_ONLY
    assert rows["demo/declarative"].classification is SemanticBoundaryClassification.DECLARATIVE_ONLY
    generic = rows["demo/generic"]
    assert generic.classification is SemanticBoundaryClassification.DELETE_CANDIDATE
    assert generic.generic_leaf_runtime and generic.generic_state_capable
    assert generic.semantic_source_files == ()
    implemented = rows["demo/implemented"]
    assert implemented.classification is SemanticBoundaryClassification.IMPLEMENTED_SEMANTIC_BOUNDARY
    assert implemented.semantic_source_files == ("providers/sqlite.py",)


def test_generic_leaf_shell_cannot_claim_implemented_semantic_boundary(tmp_path: Path) -> None:
    from research_platform.governance.architecture import classify_semantic_boundary
    from research_platform.governance.architecture.api import (
        SemanticBoundaryClaim, SemanticBoundaryClaimError, validate_semantic_boundary_claim,
    )

    evidence = classify_semantic_boundary(_semantic_boundary_fixture(tmp_path), "demo/generic")
    with pytest.raises(SemanticBoundaryClaimError, match="cannot claim implemented"):
        validate_semantic_boundary_claim(evidence, SemanticBoundaryClaim(evidence.node, implemented=True))


def test_generic_leaf_state_cannot_be_claimed_as_domain_durable_authority(tmp_path: Path) -> None:
    from research_platform.governance.architecture import classify_semantic_boundary
    from research_platform.governance.architecture.api import (
        SemanticBoundaryClaim, SemanticBoundaryClaimError, SemanticStateAuthorityKind,
        validate_semantic_boundary_claim,
    )

    evidence = classify_semantic_boundary(_semantic_boundary_fixture(tmp_path), "demo/implemented")
    with pytest.raises(SemanticBoundaryClaimError, match="generic leaf state"):
        validate_semantic_boundary_claim(
            evidence,
            SemanticBoundaryClaim(
                evidence.node, implemented=True,
                state_authority=SemanticStateAuthorityKind.GENERIC_LEAF_STATE,
            ),
        )


def test_typed_domain_authority_claim_is_accepted_for_real_boundary(tmp_path: Path) -> None:
    from research_platform.governance.architecture import classify_semantic_boundary
    from research_platform.governance.architecture.api import (
        SemanticBoundaryClaim, SemanticStateAuthorityKind, validate_semantic_boundary_claim,
    )

    evidence = classify_semantic_boundary(_semantic_boundary_fixture(tmp_path), "demo/implemented")
    validate_semantic_boundary_claim(
        evidence,
        SemanticBoundaryClaim(
            evidence.node, implemented=True,
            state_authority=SemanticStateAuthorityKind.DOMAIN_TYPED,
        ),
    )


def test_semantic_boundary_inventory_is_deterministic_and_digest_bound(tmp_path: Path) -> None:
    from research_platform.governance.architecture import classify_semantic_boundaries

    root = _semantic_boundary_fixture(tmp_path)
    first = classify_semantic_boundaries(root)
    second = classify_semantic_boundaries(root)
    assert tuple(row.node for row in first) == tuple(row.node for row in second)
    assert tuple(row.digest for row in first) == tuple(row.digest for row in second)

def test_architecture_budget_allows_signed_contraction_delta(tmp_path: Path) -> None:
    document=_multidim_budget_document("a"*64)
    document["migrations"][0]["delta"]={"top_level_systems":0,"subsystems":-1,"contract_declarations":1,"authorities":-1,"import_edges":1}
    _write_budget(tmp_path,document)
    budget=load_architecture_complexity_budget(tmp_path)
    assert budget.migrations[0].delta==ArchitectureComplexity(0,-1,1,-1,1)


def test_architecture_budget_rejects_negative_absolute_baseline(tmp_path: Path) -> None:
    document=_multidim_budget_document("a"*64)
    document["baseline"]["complexity"]["subsystems"]=-1
    _write_budget(tmp_path,document)
    with pytest.raises(ValueError,match="baseline.complexity.subsystems must be a non-negative integer"):
        load_architecture_complexity_budget(tmp_path)


def test_architecture_budget_rejects_contraction_below_zero(tmp_path: Path) -> None:
    document=_multidim_budget_document("a"*64)
    document["migrations"][0]["delta"]={"top_level_systems":0,"subsystems":-174,"contract_declarations":0,"authorities":0,"import_edges":0}
    _write_budget(tmp_path,document)
    with pytest.raises(ValueError,match="produces negative complexity: subsystems"):
        load_architecture_complexity_budget(tmp_path)


def test_v2_approval_file_decodes_signed_complexity_delta(tmp_path: Path) -> None:
    import hashlib
    delta={"top_level_systems":0,"subsystems":-1,"contract_declarations":13,"authorities":-1,"import_edges":39}
    row={
        "schema":"supervisor.architecture-migration-approval.v2",
        "migration_id":"test-reviewed-contraction", "complexity_delta":delta,
        "source_sha":"3"*40, "source_digest":"b"*64, "decision":"approved",
        "authority":"ROLE00", "scope":"architecture-complexity-migration-only",
        "review_state":"READY_FOR_REVIEW",
        "review_evidence_refs":["state/SUPERVISOR_REVIEW_GATES.md#test-signed-delta"],
        "issued_at":"2026-08-31T03:30:00+08:00",
        "note":"Synthetic signed contraction approval decode test.",
    }
    payload=json.dumps(row,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode()
    row["approval_record_sha256"]=hashlib.sha256(payload).hexdigest()
    doc={"schema":"supervisor.architecture-migration-approval-set.v1","authority":"ROLE00",
         "baseline_sha":"1"*40,"approvals":[row],"default_decision":"not_approved",
         "rule":"full complexity records bind signed architecture changes"}
    raw=(json.dumps(doc,indent=2)+"\n").encode(); target=tmp_path/"approvals-signed.json"; target.write_bytes(raw)
    loaded=load_architecture_migration_approval_set(target,expected_sha256=hashlib.sha256(raw).hexdigest())
    assert loaded.approvals[0].complexity_delta==ArchitectureComplexity(0,-1,13,-1,39)

def test_v2_signed_approval_authorizes_exact_contraction(tmp_path: Path, monkeypatch) -> None:
    pairs=(("research_platform.governance.a","research_platform.platform.b"),)
    projection=import_projection_digest(pairs,("research_platform.governance",))
    document=_multidim_budget_document(projection)
    signed=ArchitectureComplexity(0,-1,1,-1,1)
    document["migrations"][0]["delta"]={"top_level_systems":0,"subsystems":-1,"contract_declarations":1,"authorities":-1,"import_edges":1}
    _write_budget(tmp_path,document); index=_synthetic_git_index(tmp_path)
    owner=source_scope_digest(index,("research_platform.governance",))
    import research_platform.governance.architecture.budget as budget_module
    monkeypatch.setattr(budget_module,"current_architecture_complexity",lambda *,import_edges: ArchitectureComplexity(17,172,142,189,import_edges))
    def resolve(sha: str, prefixes: tuple[str,...]):
        if sha=="1"*40:
            return "2"*64,ArchitectureMigrationObservation(ArchitectureComplexity(17,173,141,190,4749),None,None)
        return "b"*64,ArchitectureMigrationObservation(ArchitectureComplexity(17,172,142,189,4750),projection,owner)
    current,budget,violations=audit_architecture_complexity_budget(
        tmp_path,import_edges=4750,import_edge_pairs=pairs,source_index=index,
        approval_set=_typed_v2_approval_set(signed),historical_observation_resolver=resolve,verify_provenance=True)
    assert violations==() and budget is not None
    assert current==ArchitectureComplexity(17,172,142,189,4750)
    assert budget.applicable_migration_ids==("test-reviewed-migration",)
    assert budget.limits==ArchitectureComplexity(17,172,142,189,4750)
