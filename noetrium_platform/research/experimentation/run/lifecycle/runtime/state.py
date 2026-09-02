from __future__ import annotations

from dataclasses import dataclass

from noetrium_platform.foundation.kernel.kernel import ExecutionContext


from ..api.contracts import RunClosed, RunRecoveryRequired


@dataclass(slots=True)
class RunState:
    closed: bool = False
    requires_recovery: bool = False
    last_context: ExecutionContext | None = None
    latest_checkpoint_id: str | None = None
    completed_cycles: int = 0

    def require_runnable(self) -> None:
        if self.closed:
            raise RunClosed("study run is closed")
        if self.requires_recovery:
            raise RunRecoveryRequired(
                "study run is in an uncertain state; close and restore from a verified checkpoint"
            )

    def mark_failed(self) -> None:
        self.requires_recovery = True

    def mark_cycle_complete(self, context: ExecutionContext, checkpoint_id: str | None) -> None:
        self.last_context = context
        self.latest_checkpoint_id = checkpoint_id or self.latest_checkpoint_id
        self.completed_cycles += 1

    def mark_closed(self) -> None:
        self.closed = True


__all__ = ["RunClosed", "RunRecoveryRequired", "RunState"]
