from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_platform.governance.api import (
    GovernanceBaselineApproval,
    GovernanceBaselineApprovalSet,
    GovernanceBaselineLane,
)
from research_platform.governance.concurrency.api import ConcurrencyBaseline, ConcurrencySnapshot
from research_platform.governance.concurrency.runtime import (
    ConcurrencyBaselineApprovalMissing,
    ConcurrencyGovernanceService,
)
from research_platform.governance.performance.api import PerformanceBaseline, PerformanceSnapshot
from research_platform.governance.performance.runtime import (
    PerformanceBaselineApprovalMissing,
    PerformanceGovernanceService,
)
from research_platform.governance.providers import (
    GovernanceBaselineApprovalError,
    load_governance_baseline_approval_set,
)
from research_platform.governance.runtime import governance_baseline_semantic_digest


def _concurrency_snapshot(*, implementation: str = "3" * 64) -> ConcurrencySnapshot:
    return ConcurrencySnapshot(
        schema_version="concurrency-snapshot.v2",
        analyzer_revision="python:python-concurrency-ast-v10",
        source_digest="2" * 64,
        hotspots=(),
        coverage=(),
        generated_unix_ns=1,
        source_authority="git",
        source_revision="1" * 40,
        analyzer_implementation_digest=implementation,
    )


def _performance_snapshot(*, implementation: str = "6" * 64) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        schema_version="performance-snapshot.v2",
        analyzer_revision="python:python-performance-ast-v4",
        source_digest="5" * 64,
        hotspots=(),
        coverage=(),
        generated_unix_ns=1,
        source_authority="git",
        source_revision="4" * 40,
        analyzer_implementation_digest=implementation,
    )


def _concurrency_baseline(snapshot: ConcurrencySnapshot) -> ConcurrencyBaseline:
    return ConcurrencyBaseline(
        schema_version="concurrency-baseline.v2",
        source_authority=snapshot.source_authority,
        source_revision=snapshot.source_revision,
        source_digest=snapshot.source_digest,
        analyzer_revision=snapshot.analyzer_revision,
        analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
        observed_blocker_fingerprints=snapshot.blocker_fingerprints,
        accepted_blocker_fingerprints=snapshot.blocker_fingerprints,
    )


def _performance_baseline(snapshot: PerformanceSnapshot) -> PerformanceBaseline:
    return PerformanceBaseline(
        schema_version="performance-baseline.v2",
        source_authority=snapshot.source_authority,
        source_revision=snapshot.source_revision,
        source_digest=snapshot.source_digest,
        analyzer_revision=snapshot.analyzer_revision,
        analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
        observed_blocker_fingerprints=snapshot.blocker_fingerprints,
        accepted_blocker_fingerprints=snapshot.blocker_fingerprints,
    )


def _service_store(baseline):
    saved = []
    return SimpleNamespace(
        load_baseline=lambda: baseline,
        publish_current=lambda _snapshot: None,
        append_history=lambda _snapshot: None,
        publish_baseline=lambda value: saved.append(value),
    ), saved


def _approval_set(approval: GovernanceBaselineApproval) -> GovernanceBaselineApprovalSet:
    return GovernanceBaselineApprovalSet(
        schema_version="governance-baseline-approval-set.v1",
        authority="ROLE00",
        approvals=(approval,),
        default_decision="not_approved",
        rule="Exact lane/source/analyzer/baseline identity only.",
    )


def _approval_for(snapshot, lane: GovernanceBaselineLane) -> GovernanceBaselineApproval:
    digest = governance_baseline_semantic_digest(
        lane=lane,
        source_revision=snapshot.source_revision or "",
        source_digest=snapshot.source_digest,
        analyzer_revision=snapshot.analyzer_revision,
        analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
        observed_blocker_fingerprints=snapshot.blocker_fingerprints,
        accepted_blocker_fingerprints=snapshot.blocker_fingerprints,
    )
    return GovernanceBaselineApproval(
        approval_id=f"{lane.value}-baseline-001",
        lane=lane,
        source_git_sha=snapshot.source_revision or "",
        source_digest=snapshot.source_digest,
        analyzer_revision=snapshot.analyzer_revision,
        analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
        baseline_digest=digest,
        decision="approved",
        authority="ROLE00",
        scope="governance-baseline-refresh",
        review_state="reviewed",
        review_evidence_refs=("state/review.json",),
        issued_at="2026-08-30T22:47:00+08:00",
        note="Reviewed exact immutable baseline replay evidence.",
        approval_record_sha256="9" * 64,
    )


def test_concurrency_legacy_baseline_stops_at_one_parent_provenance_blocker() -> None:
    current = _concurrency_snapshot()
    legacy = ConcurrencyBaseline(
        schema_version="concurrency-baseline.v1",
        source_authority="legacy",
        source_revision=None,
        source_digest="",
        analyzer_revision=current.analyzer_revision,
        analyzer_implementation_digest="",
        observed_blocker_fingerprints=(),
        accepted_blocker_fingerprints=("fake-child-debt",),
    )
    store, _saved = _service_store(legacy)
    service = ConcurrencyGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current),
        store=store,
        baseline_replay=lambda _revision: current,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "concurrency baseline provenance migration required: reviewed baseline is not concurrency-baseline.v2",
    )
    assert report.warnings == ()


def test_performance_legacy_baseline_stops_at_one_parent_provenance_blocker() -> None:
    current = _performance_snapshot()
    legacy = PerformanceBaseline(
        schema_version="performance-baseline.v1",
        source_authority="legacy",
        source_revision=None,
        source_digest="",
        analyzer_revision=current.analyzer_revision,
        analyzer_implementation_digest="",
        observed_blocker_fingerprints=(),
        accepted_blocker_fingerprints=("fake-child-debt",),
    )
    store, _saved = _service_store(legacy)
    service = PerformanceGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current),
        store=store,
        baseline_replay=lambda _revision: current,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "performance baseline provenance migration required: reviewed baseline is not performance-baseline.v2",
    )
    assert report.warnings == ()


def test_same_revision_with_changed_concurrency_implementation_identity_is_stale() -> None:
    baseline_snapshot = _concurrency_snapshot(implementation="3" * 64)
    current = _concurrency_snapshot(implementation="7" * 64)
    store, _saved = _service_store(_concurrency_baseline(baseline_snapshot))
    service = ConcurrencyGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: baseline_snapshot,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "concurrency analyzer identity changed; reviewed baseline migration required",
    )


def test_same_revision_with_changed_performance_implementation_identity_is_stale() -> None:
    baseline_snapshot = _performance_snapshot(implementation="6" * 64)
    current = _performance_snapshot(implementation="8" * 64)
    store, _saved = _service_store(_performance_baseline(baseline_snapshot))
    service = PerformanceGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: baseline_snapshot,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "performance analyzer identity changed; reviewed baseline migration required",
    )


def test_concurrency_replay_mismatch_fails_before_current_debt_diff() -> None:
    current = _concurrency_snapshot()
    baseline = replace(_concurrency_baseline(current), observed_blocker_fingerprints=("tampered",))
    store, _saved = _service_store(baseline)
    service = ConcurrencyGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: current,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "concurrency baseline observed blocker fingerprints are not reproducible from immutable source",
    )


def test_performance_replay_mismatch_fails_before_current_debt_diff() -> None:
    current = _performance_snapshot()
    baseline = replace(_performance_baseline(current), observed_blocker_fingerprints=("tampered",))
    store, _saved = _service_store(baseline)
    service = PerformanceGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: current,
    )
    _snapshot, report = service.gate()
    assert report.blockers == (
        "performance baseline observed blocker fingerprints are not reproducible from immutable source",
    )


def test_concurrency_exact_baseline_acceptance_requires_matching_role00_approval() -> None:
    current = _concurrency_snapshot()
    store, saved = _service_store(None)
    service = ConcurrencyGovernanceService(scanner=SimpleNamespace(scan=lambda: current), store=store)
    with pytest.raises(ConcurrencyBaselineApprovalMissing, match="ROLE00 exact"):
        service.accept_baseline()
    service.approval_set = _approval_set(_approval_for(current, GovernanceBaselineLane.CONCURRENCY))
    assert service.accept_baseline() == current
    assert saved == [_concurrency_baseline(current)]


def test_performance_exact_baseline_acceptance_requires_matching_role00_approval() -> None:
    current = _performance_snapshot()
    store, saved = _service_store(None)
    service = PerformanceGovernanceService(scanner=SimpleNamespace(scan=lambda: current), store=store)
    with pytest.raises(PerformanceBaselineApprovalMissing, match="ROLE00 exact"):
        service.accept_baseline()
    service.approval_set = _approval_set(_approval_for(current, GovernanceBaselineLane.PERFORMANCE))
    assert service.accept_baseline() == current
    assert saved == [_performance_baseline(current)]


def test_governance_baseline_approval_wrong_lane_contributes_zero_authority() -> None:
    current = _concurrency_snapshot()
    store, _saved = _service_store(None)
    service = ConcurrencyGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        approval_set=_approval_set(_approval_for(current, GovernanceBaselineLane.PERFORMANCE)),
    )
    with pytest.raises(ConcurrencyBaselineApprovalMissing, match="ROLE00 exact"):
        service.accept_baseline()


def test_governance_baseline_approval_file_and_record_are_digest_bound(tmp_path: Path) -> None:
    record = {
        "schema": "governance-baseline-approval.v1",
        "approval_id": "concurrency-baseline-001",
        "lane": "concurrency",
        "source_sha": "1" * 40,
        "source_digest": "2" * 64,
        "analyzer_revision": "python:python-concurrency-ast-v10",
        "analyzer_implementation_digest": "3" * 64,
        "baseline_digest": "4" * 64,
        "decision": "approved",
        "authority": "ROLE00",
        "scope": "governance-baseline-refresh",
        "review_state": "reviewed",
        "review_evidence_refs": ["state/review.json"],
        "issued_at": "2026-08-30T22:47:00+08:00",
        "note": "Reviewed immutable concurrency baseline replay evidence.",
    }
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record["approval_record_sha256"] = hashlib.sha256(canonical).hexdigest()
    document = {
        "schema": "governance-baseline-approval-set.v1",
        "authority": "ROLE00",
        "approvals": [record],
        "default_decision": "not_approved",
        "rule": "Exact lane/source/analyzer/baseline identity only.",
    }
    raw = (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = tmp_path / "approvals.json"
    path.write_bytes(raw)
    loaded = load_governance_baseline_approval_set(path, expected_sha256=hashlib.sha256(raw).hexdigest())
    assert loaded.approval_for(
        lane=GovernanceBaselineLane.CONCURRENCY,
        source_git_sha="1" * 40,
        source_digest="2" * 64,
        analyzer_revision="python:python-concurrency-ast-v10",
        analyzer_implementation_digest="3" * 64,
        baseline_digest="4" * 64,
    ) is not None
    with pytest.raises(GovernanceBaselineApprovalError, match="digest mismatch"):
        load_governance_baseline_approval_set(path, expected_sha256="0" * 64)
    tampered = json.loads(raw.decode("utf-8"))
    tampered["approvals"][0]["note"] = "tampered"
    tampered_raw = (json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(tampered_raw)
    with pytest.raises(GovernanceBaselineApprovalError, match="approval record digest mismatch"):
        load_governance_baseline_approval_set(path, expected_sha256=hashlib.sha256(tampered_raw).hexdigest())


def test_duplicate_approved_governance_baseline_identity_is_rejected() -> None:
    current = _concurrency_snapshot()
    first = _approval_for(current, GovernanceBaselineLane.CONCURRENCY)
    second = replace(first, approval_id="concurrency-baseline-002")
    with pytest.raises(ValueError, match="identities must be unique"):
        GovernanceBaselineApprovalSet(
            schema_version="governance-baseline-approval-set.v1",
            authority="ROLE00",
            approvals=(first, second),
            default_decision="not_approved",
            rule="Exact lane/source/analyzer/baseline identity only.",
        )

def test_reproducible_concurrency_observation_is_not_implicitly_accepted() -> None:
    from research_platform.governance.concurrency.api import (
        ConcurrencyFinding, ConcurrencyHotspot, ConcurrencyMetrics, ConcurrencyPriority,
    )
    finding = ConcurrencyFinding(ConcurrencyPriority.P1, "historical-risk", "must remain blocking", 2)
    hotspot = ConcurrencyHotspot(
        hotspot_id="pkg/a.py::f", relative_path="pkg/a.py", language=__import__(
            "research_platform.governance.concurrency.api", fromlist=["ConcurrencyLanguage"]
        ).ConcurrencyLanguage.PYTHON, qualified_name="f", line_start=1, line_end=2,
        metrics=ConcurrencyMetrics(), findings=(finding,),
    )
    current = replace(_concurrency_snapshot(), hotspots=(hotspot,))
    historical = current
    baseline = replace(
        _concurrency_baseline(current),
        observed_blocker_fingerprints=current.blocker_fingerprints,
        accepted_blocker_fingerprints=(),
    )
    store, _saved = _service_store(baseline)
    service = ConcurrencyGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: historical,
    )
    _snapshot, report = service.gate()
    assert not report.passed
    assert report.blockers == current.blocker_fingerprints


def test_reproducible_performance_observation_is_not_implicitly_accepted() -> None:
    from research_platform.governance.performance.api import (
        PerformanceFinding, PerformanceHotspot, PerformanceLanguage, PerformanceMetrics, PerformancePriority,
    )
    finding = PerformanceFinding(PerformancePriority.P1, "historical-risk", "must remain blocking", 20)
    hotspot = PerformanceHotspot(
        hotspot_id="pkg/a.py::f", relative_path="pkg/a.py", language=PerformanceLanguage.PYTHON,
        qualified_name="f", line_start=1, line_end=2, metrics=PerformanceMetrics(), findings=(finding,),
    )
    current = replace(_performance_snapshot(), hotspots=(hotspot,))
    historical = current
    baseline = replace(
        _performance_baseline(current),
        observed_blocker_fingerprints=current.blocker_fingerprints,
        accepted_blocker_fingerprints=(),
    )
    store, _saved = _service_store(baseline)
    service = PerformanceGovernanceService(
        scanner=SimpleNamespace(scan=lambda: current), store=store,
        baseline_replay=lambda _revision: historical,
    )
    _snapshot, report = service.gate()
    assert not report.passed
    assert report.blockers == current.blocker_fingerprints


def test_lane_implementation_digest_covers_lane_source_bytes(tmp_path: Path) -> None:
    from research_platform.governance.api import GovernanceBaselineLane
    from research_platform.governance.providers import RepositorySourceTree
    from research_platform.governance.runtime import governance_lane_implementation_digest

    source = tmp_path / "research_platform" / "governance" / "concurrency" / "runtime" / "x.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    first = governance_lane_implementation_digest(
        RepositorySourceTree(tmp_path).index(), GovernanceBaselineLane.CONCURRENCY
    )
    source.write_text("VALUE = 2\n", encoding="utf-8")
    second = governance_lane_implementation_digest(
        RepositorySourceTree(tmp_path).index(), GovernanceBaselineLane.CONCURRENCY
    )
    assert first != second


def test_lane_implementation_digest_is_line_ending_independent(tmp_path: Path) -> None:
    from research_platform.governance.api import GovernanceBaselineLane
    from research_platform.governance.providers import RepositorySourceTree
    from research_platform.governance.runtime import governance_lane_implementation_digest

    source = tmp_path / "research_platform" / "governance" / "performance" / "runtime" / "x.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"VALUE = 1\r\n")
    crlf = governance_lane_implementation_digest(
        RepositorySourceTree(tmp_path).index(), GovernanceBaselineLane.PERFORMANCE
    )
    source.write_bytes(b"VALUE = 1\n")
    lf = governance_lane_implementation_digest(
        RepositorySourceTree(tmp_path).index(), GovernanceBaselineLane.PERFORMANCE
    )
    assert crlf == lf
