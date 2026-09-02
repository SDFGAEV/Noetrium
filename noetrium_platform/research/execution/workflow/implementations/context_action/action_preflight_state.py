from __future__ import annotations

from noetrium_platform.foundation.kernel.kernel import ExecutionContext


class ActionPreflightState:
    """Tracks only which decision cycle has passed action-safety capability preflight."""

    def __init__(self) -> None:
        self._cycle_id: str | None = None

    @staticmethod
    def cycle_id(context: ExecutionContext) -> str:
        return context.decision_cycle_id or context.span_id

    def mark(self, context: ExecutionContext) -> None:
        self._cycle_id = self.cycle_id(context)

    def matches(self, context: ExecutionContext) -> bool:
        return self._cycle_id == self.cycle_id(context)

    def clear(self) -> None:
        self._cycle_id = None


__all__ = ["ActionPreflightState"]
