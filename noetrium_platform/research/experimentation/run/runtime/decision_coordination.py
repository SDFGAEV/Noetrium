from __future__ import annotations

from dataclasses import dataclass, field

from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonValue, OperationResult

from ..lifecycle.api import RunCleanupFailure, RunCleanupReport, attach_cleanup_note
from noetrium_platform.capabilities.participant.core.api import BoundParticipants, ParticipantSessionBinding
from noetrium_platform.research.experimentation.experiment.api import (
    ExperimentComponentBindingPort,
    ExperimentSpec,
    ExperimentTrialCycleExecutorPort,
)
from noetrium_platform.research.execution.decision.cycle_identity import DecisionCycleIdentity
from noetrium_platform.research.execution.decision.cycle_result import DecisionCycleResult
from noetrium_platform.research.execution.workflow.api import TrialCycleExecution
from noetrium_platform.capabilities.participant.core.api.runtime_ports import ParticipantSessionLifecyclePort


def _require_bound_participants(value: BoundParticipants | None) -> BoundParticipants:
    if value is None:
        raise RuntimeError("decision cycle participant binder returned no bound participants")
    return value


def _require_trial_execution(
    value: TrialCycleExecution | None,
) -> TrialCycleExecution:
    if value is None:
        raise RuntimeError("scientific executor returned no execution result (decision cycle trial executor)")
    return value


@dataclass(slots=True)
class _CycleState:
    context: ExecutionContext
    operations: list[OperationResult[JsonValue]] = field(default_factory=list)
    bound: BoundParticipants | None = None
    participant_sessions: list[ParticipantSessionBinding] = field(default_factory=list)
    execution: TrialCycleExecution | None = None


class DecisionCycleCoordinator:
    """One-cycle resource transaction over generic participant topology."""

    def __init__(self, binder: ExperimentComponentBindingPort, lifecycle: ParticipantSessionLifecyclePort, trial: ExperimentTrialCycleExecutorPort) -> None:
        self.binder = binder
        self.lifecycle = lifecycle
        self.trial = trial


    def _execute(self, state: _CycleState, spec: ExperimentSpec, identity: DecisionCycleIdentity, *, task: object, input_kind: str, input_payload: object) -> None:
        state.bound = _require_bound_participants(self.binder.bind(spec, state.context))
        state.operations.extend(state.bound.operation_results)
        for participant in state.bound.participants:
            binding, operation = self.lifecycle.open_participant(participant, state.context, identity.session_id)
            state.participant_sessions.append(binding)
            state.operations.append(operation)
        state.execution = _require_trial_execution(self.trial.execute(
            bound=state.bound,
            participant_sessions=tuple(state.participant_sessions),
            context=state.context,
            task=task,
            input_kind=input_kind,
            input_payload=input_payload,
        ))
        state.operations.extend(state.execution.operation_results)
        state.context = state.execution.final_context

    def _cleanup(self, state: _CycleState, session_id: str) -> RunCleanupReport:
        rows = tuple(
            self.lifecycle.close_participant(binding, state.context, session_id)
            for binding in reversed(state.participant_sessions)
        )
        report = RunCleanupReport(rows)
        state.operations.extend(report.results)
        return report

    @staticmethod
    def _result(state: _CycleState, identity: DecisionCycleIdentity) -> DecisionCycleResult:
        if state.execution is None:
            raise RuntimeError("decision cycle execution result is required before projection")
        return DecisionCycleResult(
            identity.run_id,
            identity.decision_cycle_id,
            state.execution.context_text,
            state.execution.primary_result,
            tuple(state.operations),
            identity,
        )

    def run(self, spec: ExperimentSpec, identity: DecisionCycleIdentity, *, task: object, input_kind: str, input_payload: object) -> DecisionCycleResult:
        state = _CycleState(identity_context(identity, spec))
        primary: BaseException | None = None
        try:
            self._execute(state, spec, identity, task=task, input_kind=input_kind, input_payload=input_payload)
        except BaseException as exc:
            primary = exc
        cleanup = self._cleanup(state, identity.session_id)
        if primary is not None:
            attach_cleanup_note(primary, cleanup)
            raise primary
        if cleanup.failures:
            raise RunCleanupFailure(cleanup, trial_completed=state.execution is not None)
        return self._result(state, identity)


def identity_context(identity: DecisionCycleIdentity, spec: ExperimentSpec) -> ExecutionContext:
    return ExecutionContext(
        run_id=identity.run_id,
        trace_id=identity.trace_id,
        span_id=identity.decision_cycle_id,
        study_id=spec.study_id,
        task_id=identity.task_id,
        decision_cycle_id=identity.decision_cycle_id,
    )
