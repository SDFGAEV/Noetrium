from __future__ import annotations

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.core.api import BoundParticipants, ParticipantSessionBinding
from research_platform.execution.workflow.api import (
    EffectIntentOperationPort,
    OperationDispatchPort,
    TrialCycleExecution,
    WorkflowSurfaceBindingContext,
    WorkflowSurfaceFactory,
    workflow_surface_id,
)
from research_platform.experimentation.experiment.api import ExperimentTrialProtocol

from .workflow_surfaces import ExperimentWorkflowSurfaceRegistry


class ExperimentTrialCycleExecutor:
    """Binds generic operation ports to an injected trial protocol."""

    def __init__(
        self,
        dispatcher: OperationDispatchPort,
        trial_protocol: ExperimentTrialProtocol,
        *,
        effect_intents: EffectIntentOperationPort | None = None,
        workflow_surface_factories: tuple[WorkflowSurfaceFactory, ...] = (),
    ) -> None:
        self.dispatcher = dispatcher
        self.trial_protocol = trial_protocol
        self.effect_intents = effect_intents
        self._surface_registry = ExperimentWorkflowSurfaceRegistry(workflow_surface_factories)

    def execute(
        self,
        *,
        bound: BoundParticipants,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        context: ExecutionContext,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> TrialCycleExecution:
        surface_context = WorkflowSurfaceBindingContext(
            self.dispatcher,
            bound,
            participant_sessions,
            self.effect_intents,
        )
        surface = self._surface_registry.bind(workflow_surface_id(self.trial_protocol), surface_context)
        result = self.trial_protocol.run(
            surface,
            context,
            task=task,
            input_kind=input_kind,
            input_payload=input_payload,
        )
        if not isinstance(result, TrialCycleExecution):
            raise TypeError("ExperimentTrialProtocol must return TrialCycleExecution")
        return result


__all__ = ["ExperimentTrialCycleExecutor"]
