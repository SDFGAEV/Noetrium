from __future__ import annotations

from collections.abc import Mapping

from research_platform.reliability.effect.api import (
    EffectAlreadyConsumed,
    EffectIntent,
    EffectIntentPhase,
    EffectIntentRecord,
    EffectRecoveryAnchorMissing,
)
from research_platform.environment.runtime.api import (
    ActionNotApplied,
    ActionRequest,
)
from research_platform.platform.kernel import ExecutionContext, JsonValue, OperationResult

from research_platform.execution.workflow.api import EffectIntentOperationPort
from research_platform.participant.core.api import BoundParticipants
from .action_effect_identity import build_action_effect_intent
from research_platform.execution.workflow.api import OperationDispatchPort


class ActionSlotGuard:
    """Owns logical action-slot inspection and replay/recovery-anchor guards.

    The slot identity intentionally excludes the pre-action Environment generation so an
    earlier PREPARED/terminal action remains discoverable after the external world changes.
    Exact world-cut identity is frozen later by ``ActionAuthorizationBuilder``.
    """

    def __init__(
        self,
        dispatcher: OperationDispatchPort,
        bound: BoundParticipants,
        *,
        journal_ops: EffectIntentOperationPort | None,
        journal_durability: str | None,
    ) -> None:
        self._dispatcher = dispatcher
        self._bound = bound
        self._journal_ops = journal_ops
        self._journal_durability = journal_durability
        self._preflight_existing: EffectIntentRecord | None = None

    @staticmethod
    def _dc(context: ExecutionContext) -> str:
        return context.decision_cycle_id or context.span_id

    @property
    def nonterminal_candidate(self) -> EffectIntentRecord | None:
        row = self._preflight_existing
        return row if row is not None and not row.phase.terminal else None

    @property
    def preflight_existing_phase(self) -> EffectIntentPhase | None:
        return self._preflight_existing.phase if self._preflight_existing is not None else None

    def preflight_slot(
        self, *, action_type: str, action_payload: object, context: ExecutionContext
    ) -> tuple[OperationResult[JsonValue], ...]:
        self._preflight_existing = None
        if self._journal_ops is None:
            return ()
        dc = self._dc(context)
        request = ActionRequest(f"action_{dc}", action_type, action_payload, context)
        intent = build_action_effect_intent(
            request,
            operation_id=f"{dc}:environment.act",
            provider_component=self._bound.component("environment"),
        )
        rows: list[OperationResult[JsonValue]] = []
        _, scope_operation = self._journal_ops.require_scope_clear(intent, context)
        rows.append(scope_operation)
        existing, inspect_operation = self._journal_ops.inspect(intent, context)
        rows.append(inspect_operation)
        self._preflight_existing = existing
        if existing is None:
            return tuple(rows)
        guard = self.guard_existing_intent(existing.phase, context)
        if guard is not None:
            rows.append(guard)
        recovery_guard = self.guard_nonterminal_recovery_anchor(existing.phase, context)
        if recovery_guard is not None:
            rows.append(recovery_guard)
        return tuple(rows)

    @staticmethod
    def _require_existing_intent_replay_allowed(phase: EffectIntentPhase) -> str:
        if phase is EffectIntentPhase.CONSUMED:
            raise EffectAlreadyConsumed(
                "exact action intent is already CONSUMED by trial state; restore/return prior cycle result instead of replay"
            )
        if phase is EffectIntentPhase.NOT_APPLIED:
            raise ActionNotApplied(
                "exact action intent was previously proven NOT_APPLIED; a new action decision is required"
            )
        return phase.value

    def guard_existing_intent(
        self, phase: EffectIntentPhase, context: ExecutionContext
    ) -> OperationResult[JsonValue] | None:
        if not phase.terminal:
            return None
        dc = self._dc(context)
        operation = self._dispatcher.dispatch(
            root_context=context,
            operation_id=f"{dc}:environment.effect.replay_guard",
            operation_type="environment.effect.replay_guard",
            target=self._journal_ops.component_identity,
            payload={"phase": phase.value},
            payload_schema="environment.effect.replay_guard.v1",
            handler=lambda request: self._require_existing_intent_replay_allowed(
                EffectIntentPhase(str(request.payload["phase"]))
            ),
        )
        self._dispatcher.require(operation)
        return operation

    def guard_nonterminal_recovery_anchor(
        self, phase: EffectIntentPhase, context: ExecutionContext
    ) -> OperationResult[JsonValue] | None:
        if phase.terminal or self._journal_durability != "crash_durable" or context.checkpoint_id:
            return None
        dc = self._dc(context)
        operation = self._dispatcher.dispatch(
            root_context=context,
            operation_id=f"{dc}:environment.effect.recovery_anchor_guard",
            operation_type="environment.effect.recovery_anchor_guard",
            target=self._journal_ops.component_identity,
            payload={"phase": phase.value, "checkpoint_id": context.checkpoint_id},
            payload_schema="environment.effect.recovery_anchor_guard.v1",
            handler=lambda request: self._require_recovery_anchor(request.payload),
        )
        self._dispatcher.require(operation)
        return operation

    @staticmethod
    def _require_recovery_anchor(payload: Mapping[str, JsonValue]) -> str:
        if not payload.get("checkpoint_id"):
            raise EffectRecoveryAnchorMissing(
                "crash-durable non-terminal action recovery requires a verified pre-cycle checkpoint anchor"
            )
        return str(payload["checkpoint_id"])


__all__ = ["ActionSlotGuard"]
