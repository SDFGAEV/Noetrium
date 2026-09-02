from __future__ import annotations

from noetrium_platform.capabilities.environment.runtime.api import ActionResult, Observation
from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonValue, OperationResult
from noetrium_platform.capabilities.participant.method.api import RecallRequest, RecallResult

from .action_preflight_state import ActionPreflightState
from .committed_cycle_recovery import CommittedCycleRecoveryCoordinator
from .completion_recovery import CommittedCycleRecovery
from noetrium_platform.capabilities.participant.core.api import BoundParticipants, ParticipantSessionBinding
from .method_completion import MethodCompletionAdapter
from noetrium_platform.research.execution.workflow.api import (
    EffectIntentOperationPort,
    OperationDispatchPort,
    WorkflowParticipantRequirementError,
)
from .safe_action import SafeEnvironmentActionExecutor
from .contracts import StudyTaskCompletionExecution


class ContextActionTrialOperations:
    """Method+Environment operation surface only; no Agent/Capability dependencies."""

    def __init__(
        self,
        dispatcher: OperationDispatchPort,
        bound: BoundParticipants,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        *,
        effect_intents: EffectIntentOperationPort | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        by_role = {row.participant.role: row for row in participant_sessions}
        method = by_role.get("method")
        environment = by_role.get("environment")
        if method is None or environment is None:
            missing = [role for role, row in (("method", method), ("environment", environment)) if row is None]
            raise WorkflowParticipantRequirementError(
                f"context_action workflow requires participant role(s): {','.join(missing)}"
            )
        self._method = method
        self._environment = environment
        self._effect_journal_durability = effect_intents.durability if effect_intents is not None else None
        self._safe_actions = SafeEnvironmentActionExecutor(
            dispatcher,
            bound,
            environment.session,
            effect_intents=effect_intents,
        )
        self._method_completion = MethodCompletionAdapter(
            dispatcher,
            bound,
            method.session,
            effect_journal_durability=self._effect_journal_durability,
        )
        self._committed_recovery = CommittedCycleRecoveryCoordinator(
            self._method_completion, self._safe_actions
        )
        self._preflight_state = ActionPreflightState()

    @staticmethod
    def _dc(context: ExecutionContext) -> str:
        return context.decision_cycle_id or context.span_id

    def observe(self, context: ExecutionContext) -> tuple[Observation, OperationResult[JsonValue]]:
        dc = self._dc(context)
        operation = self._dispatcher.dispatch(
            root_context=context,
            operation_id=f"{dc}:environment.observe",
            operation_type="environment.observe",
            target=self._environment.participant.component,
            payload={"session_id": getattr(self._method.session, "session_id", "")},
            payload_schema="environment.observe.request.v1",
            handler=lambda request: self._environment.session.observe(request.context),
        )
        return self._dispatcher.require(operation), operation

    def ingest(self, observation: Observation, context: ExecutionContext) -> OperationResult[JsonValue]:
        dc = self._dc(context)
        operation = self._dispatcher.dispatch(
            root_context=context,
            operation_id=f"{dc}:method.ingest",
            operation_type="method.ingest",
            target=self._method.participant.component,
            payload=observation,
            payload_schema="method.ingest.request.v1",
            handler=lambda request: self._method.session.ingest(request.payload, request.context),
        )
        self._dispatcher.require(operation)
        return operation

    def recall(self, task_text: str, context: ExecutionContext) -> tuple[RecallResult, OperationResult[JsonValue]]:
        dc = self._dc(context)
        request = RecallRequest(task_text, context)
        operation = self._dispatcher.dispatch(
            root_context=context,
            operation_id=f"{dc}:method.recall",
            operation_type="method.recall",
            target=self._method.participant.component,
            payload=request,
            payload_schema="method.recall.request.v1",
            handler=lambda envelope: self._method.session.recall(
                RecallRequest(envelope.payload.intent, envelope.context, envelope.payload.limit)
            ),
        )
        return self._dispatcher.require(operation), operation

    def preflight_action(
        self, action_type: str, action_payload: JsonValue, context: ExecutionContext
    ) -> tuple[OperationResult[JsonValue], ...]:
        rows: list[OperationResult[JsonValue]] = list(
            self._safe_actions.preflight_action_slot(
                action_type=action_type, action_payload=action_payload, context=context
            )
        )
        method_preflight = self._method_completion.preflight(context)
        if method_preflight is not None:
            rows.append(method_preflight)
        self._preflight_state.mark(context)
        return tuple(rows)

    def try_recover_committed_cycle(
        self, action_type: str, action_payload: JsonValue, context: ExecutionContext
    ) -> CommittedCycleRecovery | None:
        recovered = self._committed_recovery.recover(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
        )
        if recovered is not None:
            self._preflight_state.clear()
        return recovered

    def act(
        self, action_type: str, action_payload: JsonValue, context: ExecutionContext
    ) -> tuple[ActionResult, tuple[OperationResult[JsonValue], ...]]:
        rows: list[OperationResult[JsonValue]] = []
        if not self._preflight_state.matches(context):
            rows.extend(self.preflight_action(action_type, action_payload, context))
        prepared = self._safe_actions.prepare_action(
            action_type=action_type,
            action_payload=action_payload,
            context=context,
            capability_checked=True,
        )
        execution = self._safe_actions.execute_prepared(prepared)
        rows.extend(execution.operation_results)
        return execution.result, tuple(rows)

    def task_completed(
        self, action_result: ActionResult, context: ExecutionContext
    ) -> StudyTaskCompletionExecution:
        completed = self._method_completion.complete(action_result, context)
        rows: list[OperationResult[JsonValue]] = [completed.operation]
        consumed = self._safe_actions.confirm_trial_commit(context, completed.consumption)
        if consumed is not None:
            rows.append(consumed)
        return StudyTaskCompletionExecution(completed.receipt, tuple(rows))


__all__ = ["ContextActionTrialOperations"]
