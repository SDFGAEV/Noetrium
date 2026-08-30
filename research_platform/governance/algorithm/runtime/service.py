from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_platform.governance.algorithm.api import (
    AlgorithmDiff,
    AlgorithmGateReport,
    AlgorithmGovernanceApprovalSet,
    AlgorithmSnapshot,
)
from research_platform.governance.algorithm.api.ports import AlgorithmSnapshotStorePort
from .diff import gate_against_baseline
from .provenance import (
    algorithm_snapshot_semantic_digest,
    baseline_provenance_blocker,
    exact_snapshot_provenance_error,
)
from .scanner import AlgorithmScanner


class AlgorithmBaselineMissing(RuntimeError):
    pass


class AlgorithmBaselineApprovalMissing(RuntimeError):
    pass


def _empty_diff() -> AlgorithmDiff:
    return AlgorithmDiff(added=(), removed=(), changed=(), moved=())


@dataclass(slots=True)
class AlgorithmGovernanceService:
    scanner: AlgorithmScanner
    store: AlgorithmSnapshotStorePort
    baseline_replay: Callable[[str], AlgorithmSnapshot] | None = None
    approval_set: AlgorithmGovernanceApprovalSet | None = None

    def scan(self, *, persist: bool = True) -> AlgorithmSnapshot:
        snapshot = self.scanner.scan()
        if persist:
            self.store.publish_current(snapshot)
            self.store.append_history(snapshot)
        return snapshot

    def accept_baseline(self) -> AlgorithmSnapshot:
        snapshot = self.scan(persist=True)
        if snapshot.source_authority == "git":
            error = exact_snapshot_provenance_error(snapshot, label="candidate algorithm baseline")
            if error is not None:
                raise AlgorithmBaselineApprovalMissing(error)
            digest = algorithm_snapshot_semantic_digest(snapshot)
            approval = (
                self.approval_set.baseline_approval_for(
                    source_git_sha=snapshot.source_revision,
                    source_digest=snapshot.source_digest,
                    analyzer_revision=snapshot.analyzer_revision,
                    analyzer_implementation_digest=snapshot.analyzer_implementation_digest,
                    snapshot_digest=digest,
                )
                if self.approval_set is not None
                else None
            )
            if approval is None:
                raise AlgorithmBaselineApprovalMissing(
                    "ROLE00 exact algorithm baseline approval is missing for this source/analyzer/snapshot identity"
                )
        self.store.publish_baseline(snapshot)
        return snapshot

    def gate(self) -> tuple[AlgorithmSnapshot, AlgorithmGateReport]:
        baseline = self.store.load_baseline()
        if baseline is None:
            raise AlgorithmBaselineMissing("algorithm baseline is missing; reviewed baseline required")
        current = self.scan(persist=True)
        if current.source_authority == "git":
            blocker = baseline_provenance_blocker(
                baseline, current, replay=self.baseline_replay
            )
            if blocker is not None:
                return current, AlgorithmGateReport(
                    passed=False, blockers=(blocker,), warnings=(), diff=_empty_diff()
                )
        return current, gate_against_baseline(
            baseline, current, approval_set=self.approval_set
        )


__all__ = [
    "AlgorithmBaselineApprovalMissing",
    "AlgorithmBaselineMissing",
    "AlgorithmGovernanceService",
]
