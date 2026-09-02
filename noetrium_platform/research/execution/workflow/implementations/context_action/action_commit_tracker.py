from __future__ import annotations

from noetrium_platform.infrastructure.reliability.effect.api import EffectCompletionEvidence, EffectIntent
from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonValue, OperationResult

from noetrium_platform.research.execution.workflow.api import EffectIntentOperationPort


class ActionCommitTracker:
    """Owns the sole cross-call link between an external action intent and Method commit.

    No effect execution or recovery capability is available here.  The tracker can only
    remember which exact intent is awaiting trial consumption and terminalize that
    intent after Method authority supplies ``EffectCompletionEvidence``.
    """

    def __init__(self, journal_ops: EffectIntentOperationPort | None) -> None:
        self._journal_ops = journal_ops
        self._active_intent: EffectIntent | None = None

    @property
    def active_intent(self) -> EffectIntent | None:
        return self._active_intent

    def activate(self, intent: EffectIntent | None) -> None:
        self._active_intent = intent

    def consume(
        self,
        context: ExecutionContext,
        consumption: EffectCompletionEvidence,
    ) -> OperationResult[JsonValue] | None:
        intent = self._active_intent
        if intent is None or self._journal_ops is None:
            return None
        _, operation = self._journal_ops.record_consumed(intent, consumption, context)
        self._active_intent = None
        return operation


__all__ = ["ActionCommitTracker"]
