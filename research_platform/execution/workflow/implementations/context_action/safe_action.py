from __future__ import annotations

from research_platform.reliability.effect.api import EffectCompletionEvidence, EffectIntentPhase
from research_platform.environment.runtime.api import ActionNotApplied, ActionRecoveryRequired
from research_platform.platform.kernel import ExecutionContext, JsonValue, OperationResult

from .action_assembly import ActionSafetyAssembly
from .action_contracts import ActionSafetyPermit, PreparedSafeAction, SafeActionExecution
from research_platform.participant.core.api import BoundParticipants
from .effect_safety import EffectSafetyPolicy
from research_platform.execution.workflow.api import EffectIntentOperationPort, OperationDispatchPort


class SafeEnvironmentActionExecutor:
    """Public façade over the independently composed action-safety subsystem."""

    def __init__(
        self,
        dispatcher: OperationDispatchPort,
        bound: BoundParticipants,
        environment_session: object,
        *,
        effect_intents: EffectIntentOperationPort | None = None,
        effect_policy: type[EffectSafetyPolicy] = EffectSafetyPolicy,
    ) -> None:
        self._runtime = ActionSafetyAssembly(
            dispatcher,
            bound,
            environment_session,
            effect_intents=effect_intents,
            effect_policy=effect_policy,
        ).build()

    def preflight_capability(self, context: ExecutionContext) -> tuple[OperationResult[JsonValue], ...]:
        return self._runtime.preparation.preflight_capability(context)

    def preflight_action_slot(
        self, *, action_type: str, action_payload: object, context: ExecutionContext
    ) -> tuple[OperationResult[JsonValue], ...]:
        return self._runtime.preparation.preflight_action_slot(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
        )

    @property
    def has_nonterminal_recovery_candidate(self) -> bool:
        return self._runtime.preparation.nonterminal_candidate is not None

    @property
    def preflight_existing_phase(self) -> EffectIntentPhase | None:
        return self._runtime.preparation.preflight_existing_phase

    def prepare_action(
        self,
        *,
        action_type: str,
        action_payload: object,
        context: ExecutionContext,
        capability_checked: bool = False,
    ) -> PreparedSafeAction:
        return self._runtime.preparation.prepare_action(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
            capability_checked=capability_checked,
        )

    def confirm_trial_commit(
        self,
        context: ExecutionContext,
        consumption: EffectCompletionEvidence,
    ) -> OperationResult[JsonValue] | None:
        return self._runtime.commit_tracker.consume(context, consumption)

    def recover_committed_action(
        self,
        *,
        action_type: str,
        action_payload: object,
        context: ExecutionContext,
    ) -> SafeActionExecution:
        return self._runtime.committed_recovery.recover(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
        )

    def execute(
        self,
        *,
        action_type: str,
        action_payload: object,
        context: ExecutionContext,
    ) -> SafeActionExecution:
        early_rows = self.preflight_action_slot(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
        )
        prepared = self.prepare_action(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
            capability_checked=True,
        )
        execution = self.execute_prepared(prepared)
        return SafeActionExecution(
            execution.result,
            tuple(early_rows) + execution.operation_results,
            execution.replayed_from_intent,
        )

    def execute_prepared(self, prepared: PreparedSafeAction) -> SafeActionExecution:
        outcome = self._runtime.execution.execute_prepared(prepared)
        self._runtime.commit_tracker.activate(outcome.active_intent)
        return outcome.execution


__all__ = [
    "ActionNotApplied",
    "ActionRecoveryRequired",
    "ActionSafetyPermit",
    "PreparedSafeAction",
    "SafeActionExecution",
    "SafeEnvironmentActionExecutor",
]
