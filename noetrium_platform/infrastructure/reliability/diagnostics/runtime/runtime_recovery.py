from __future__ import annotations

from noetrium_platform.infrastructure.reliability.recovery.api import RecoveryDecisionReport
from noetrium_platform.evidence.observability.status.api import PlatformStatus

from .runtime_recovery_classifier import classify_snapshot_recovery


class RuntimeRecoveryDecisionService:
    """Pure status-to-recovery routing. It observes no stores and performs no effects."""

    def plan(self, status: PlatformStatus) -> RecoveryDecisionReport:
        return RecoveryDecisionReport(
            tuple(
                recommendation
                for snapshot in status.snapshots
                for recommendation in classify_snapshot_recovery(snapshot)
            )
        )


__all__ = ["RuntimeRecoveryDecisionService"]
