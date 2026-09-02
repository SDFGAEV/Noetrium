from __future__ import annotations

import hashlib

import pytest

from research_platform.data.query.api import (
    ResearchDimension,
    ResearchDimensionKind,
    ResearchResultKind,
    ResearchResultQuery,
    ResearchSourceDisposition,
)
from research_platform.experimentation.run.control.composition import RunControlResearchResultSource
from research_platform.experimentation.run.api import RunArtifactKind, RunArtifactSnapshotReceipt
from research_platform.experimentation.run.control.api import (
    RunControlAction,
    RunControlEventReceipt,
    RunControlNotFound,
    RunControlPhase,
    RunControlRecordKind,
    RunControlReceipt,
    RunControlTarget,
    RunEvidenceValidity,
    RunExecutionOutcome,
    RunOutcomeProjection,
    RunScientificValidity,
    RunTaskOutcome,
)
from research_platform.experimentation.run.manifest.api import EvidenceBundleReceipt
from research_platform.scope.api import ScopeIdentity, ScopeKind


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


RUN_ID = "run-1"
MANIFEST_DIGEST = _sha("manifest")
SCOPE = ScopeIdentity(ScopeKind.RUN, RUN_ID)


def _receipt(*, with_evidence: bool = True) -> RunControlReceipt:
    evidence = None
    if with_evidence:
        artifact = RunArtifactSnapshotReceipt(
            RUN_ID,
            "evidence/bundle-1/manifest.json",
            RunArtifactKind.EVIDENCE,
            _sha("generation"),
            _sha("manifest-content"),
            10,
            None,
        )
        evidence = EvidenceBundleReceipt(
            "bundle-1",
            RUN_ID,
            MANIFEST_DIGEST,
            artifact,
        )
    event = RunControlEventReceipt(
        RUN_ID,
        2,
        RunControlRecordKind.TERMINAL,
        1,
        RunControlAction.EVIDENCE if evidence else RunControlAction.RUN,
        RunControlPhase.RUNNING,
        _sha("operation"),
        _sha("event"),
    )
    return RunControlReceipt(
        RunControlAction.EVIDENCE if evidence else RunControlAction.RUN,
        RUN_ID,
        _sha("identity"),
        MANIFEST_DIGEST,
        RunControlPhase.RUNNING,
        1,
        None,
        None,
        evidence,
        RunOutcomeProjection(
            RunExecutionOutcome.IN_PROGRESS,
            RunTaskOutcome.NOT_EVALUATED,
            RunEvidenceValidity.FINALIZED_VALID if evidence else RunEvidenceValidity.NOT_OBSERVED,
            RunScientificValidity.NOT_EVALUATED,
        ),
        event,
    )


class _Port:
    def __init__(self, receipt: RunControlReceipt | None = None) -> None:
        self.receipt = receipt

    def execute(self, request):
        assert request.target == RunControlTarget(RUN_ID, MANIFEST_DIGEST)
        if self.receipt is None:
            raise RunControlNotFound("missing run control")
        return self.receipt


def test_run_control_source_projects_typed_run_and_evidence_authority() -> None:
    source = RunControlResearchResultSource(
        _Port(_receipt()),
        run_id=RUN_ID,
        run_manifest_digest=MANIFEST_DIGEST,
        scope=SCOPE,
    )
    query = ResearchResultQuery(
        dimensions=(ResearchDimension(ResearchDimensionKind.RUN, RUN_ID),),
        kinds=(ResearchResultKind.RUN, ResearchResultKind.EVIDENCE),
    )
    first = source.snapshot(query)
    second = source.snapshot(query)
    assert first.source_id == source.source_id
    assert first.cut == second.cut
    assert {row.reference.kind for row in first.records} == {
        ResearchResultKind.RUN,
        ResearchResultKind.EVIDENCE,
    }
    run = next(row for row in first.records if row.reference.kind is ResearchResultKind.RUN)
    evidence = next(row for row in first.records if row.reference.kind is ResearchResultKind.EVIDENCE)
    assert run.content_sha256 == _receipt().receipt_digest
    assert evidence.lineage == (run.reference,)


def test_run_control_source_reports_missing_authority_as_unavailable() -> None:
    source = RunControlResearchResultSource(
        _Port(),
        run_id=RUN_ID,
        run_manifest_digest=MANIFEST_DIGEST,
        scope=SCOPE,
    )
    from research_platform.data.query.cross.composition import compose

    page = compose((source,)).query(
        ResearchResultQuery(kinds=(ResearchResultKind.RUN,))
    )
    assert page.complete is False
    assert page.records == ()
    assert page.sources[0].disposition is ResearchSourceDisposition.UNAVAILABLE
    assert page.sources[0].diagnostic_code == "RUN_CONTROL_NOT_FOUND"


def test_run_control_source_rejects_scope_and_receipt_identity_drift() -> None:
    with pytest.raises(ValueError):
        RunControlResearchResultSource(
            _Port(_receipt(with_evidence=False)),
            run_id=RUN_ID,
            run_manifest_digest=MANIFEST_DIGEST,
            scope=ScopeIdentity(ScopeKind.STUDY, "study-1"),
        )

    class ForeignPort:
        def execute(self, request):
            del request
            return RunControlReceipt(
                RunControlAction.RUN,
                "foreign-run",
                _sha("identity"),
                MANIFEST_DIGEST,
                RunControlPhase.RUNNING,
                1,
                None,
                None,
                None,
                RunOutcomeProjection(
                    RunExecutionOutcome.IN_PROGRESS,
                    RunTaskOutcome.NOT_EVALUATED,
                    RunEvidenceValidity.NOT_OBSERVED,
                    RunScientificValidity.NOT_EVALUATED,
                ),
                RunControlEventReceipt(
                    "foreign-run", 2, RunControlRecordKind.TERMINAL, 1,
                    RunControlAction.RUN, RunControlPhase.RUNNING,
                    _sha("operation"), _sha("event"),
                ),
            )

    source = RunControlResearchResultSource(
        ForeignPort(),
        run_id=RUN_ID,
        run_manifest_digest=MANIFEST_DIGEST,
        scope=SCOPE,
    )
    with pytest.raises(RuntimeError, match="identity"):
        source.snapshot(ResearchResultQuery())
