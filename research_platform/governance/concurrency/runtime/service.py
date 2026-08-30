from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_platform.governance.api import GovernanceBaselineApprovalSet, GovernanceBaselineLane
from research_platform.governance.runtime import governance_baseline_semantic_digest
from research_platform.governance.concurrency.api import ConcurrencyBaseline, ConcurrencyGateReport, ConcurrencySnapshot
from research_platform.governance.concurrency.api.ports import ConcurrencySnapshotStorePort
from .scanner import ConcurrencyScanner


class ConcurrencyBaselineMissing(RuntimeError):
    pass


class ConcurrencyBaselineApprovalMissing(RuntimeError):
    pass


def _baseline_from_snapshot(snapshot: ConcurrencySnapshot) -> ConcurrencyBaseline:
    return ConcurrencyBaseline(
        schema_version="concurrency-baseline.v2",
        source_authority=snapshot.source_authority,
        source_revision=snapshot.source_revision,
        source_digest=snapshot.source_digest,
        analyzer_revision=snapshot.analyzer_revision,
        analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
        blocker_fingerprints=snapshot.blocker_fingerprints,
    )


def _baseline_digest(baseline: ConcurrencyBaseline) -> str:
    if baseline.source_revision is None:
        return ""
    return governance_baseline_semantic_digest(
        lane=GovernanceBaselineLane.CONCURRENCY,
        source_revision=baseline.source_revision,
        source_digest=baseline.source_digest,
        analyzer_revision=baseline.analyzer_revision,
        analyzer_implementation_digest=baseline.analyzer_implementation_digest,
        blocker_fingerprints=baseline.blocker_fingerprints,
    )


def _provenance_blocker(
    baseline: ConcurrencyBaseline,
    current: ConcurrencySnapshot,
    replay: Callable[[str], ConcurrencySnapshot] | None,
) -> str | None:
    if baseline.schema_version != "concurrency-baseline.v2":
        return "concurrency baseline provenance migration required: reviewed baseline is not concurrency-baseline.v2"
    if baseline.source_authority != "git" or baseline.source_revision is None or not baseline.source_digest:
        return "concurrency baseline provenance migration required: baseline is not bound to immutable Git source"
    if not baseline.analyzer_implementation_digest:
        return "concurrency baseline provenance migration required: analyzer implementation identity is missing"
    if (
        baseline.analyzer_revision != current.analyzer_revision
        or baseline.analyzer_implementation_digest != current.analyzer_implementation_digest
    ):
        return "concurrency analyzer identity changed; reviewed baseline migration required"
    if replay is None:
        return "concurrency baseline provenance replay is unavailable"
    historical = replay(baseline.source_revision)
    if historical.source_digest != baseline.source_digest:
        return "concurrency baseline source digest is not reproducible from its Git revision"
    if historical.analyzer_revision != baseline.analyzer_revision:
        return "concurrency baseline analyzer revision is not reproducible"
    if historical.analyzer_implementation_digest != baseline.analyzer_implementation_digest:
        return "concurrency baseline analyzer implementation identity is not reproducible"
    if historical.blocker_fingerprints != baseline.blocker_fingerprints:
        return "concurrency baseline blocker fingerprints are not reproducible from immutable source"
    return None


@dataclass(slots=True)
class ConcurrencyGovernanceService:
    scanner: ConcurrencyScanner
    store: ConcurrencySnapshotStorePort
    baseline_replay: Callable[[str], ConcurrencySnapshot] | None = None
    approval_set: GovernanceBaselineApprovalSet | None = None

    def scan(self, *, persist: bool = True) -> ConcurrencySnapshot:
        snapshot=self.scanner.scan()
        if persist:
            self.store.publish_current(snapshot); self.store.append_history(snapshot)
        return snapshot

    def accept_baseline(self) -> ConcurrencySnapshot:
        snapshot=self.scan(persist=True)
        baseline=_baseline_from_snapshot(snapshot)
        if snapshot.source_authority == "git":
            if snapshot.source_revision is None or not snapshot.analyzer_implementation_digest:
                raise ConcurrencyBaselineApprovalMissing("candidate concurrency baseline lacks exact Git/analyzer identity")
            digest=_baseline_digest(baseline)
            approval=(
                self.approval_set.approval_for(
                    lane=GovernanceBaselineLane.CONCURRENCY,
                    source_git_sha=snapshot.source_revision,
                    source_digest=snapshot.source_digest,
                    analyzer_revision=snapshot.analyzer_revision,
                    analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
                    baseline_digest=digest,
                )
                if self.approval_set is not None else None
            )
            if approval is None:
                raise ConcurrencyBaselineApprovalMissing(
                    "ROLE00 exact concurrency baseline approval is missing for this source/analyzer/baseline identity"
                )
        self.store.publish_baseline(baseline)
        return snapshot

    def gate(self) -> tuple[ConcurrencySnapshot, ConcurrencyGateReport]:
        snapshot=self.scan(persist=True)
        baseline=self.store.load_baseline()
        if baseline is None:
            raise ConcurrencyBaselineMissing("concurrency baseline missing")
        if snapshot.source_authority == "git":
            blocker=_provenance_blocker(baseline,snapshot,self.baseline_replay)
            if blocker is not None:
                return snapshot, ConcurrencyGateReport(False,(blocker,),())
        current=set(snapshot.blocker_fingerprints); accepted=set(baseline.blocker_fingerprints)
        new=tuple(sorted(current-accepted))
        parse_errors=sum(row.parse_errors for row in snapshot.coverage)
        blockers=list(new)
        if parse_errors:
            blockers.append(f"concurrency analyzer parse errors: {parse_errors}")
        if snapshot.source_authority != "git" and baseline.analyzer_revision != snapshot.analyzer_revision:
            blockers.append("concurrency analyzer revision changed; baseline must be reviewed and re-accepted")
        warnings=tuple(sorted(accepted-current))
        return snapshot, ConcurrencyGateReport(not blockers, tuple(blockers), warnings)


__all__ = [
    "ConcurrencyBaselineApprovalMissing",
    "ConcurrencyBaselineMissing",
    "ConcurrencyGovernanceService",
]
