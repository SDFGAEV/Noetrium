from __future__ import annotations

from research_platform.reliability.effect.api import EffectIntentJournal
from research_platform.platform.kernel import OperationExecutor
from research_platform.participant.core.api.lifecycle import ParticipantLifecycleAdapter, ParticipantLifecycleAdapterRegistry
from research_platform.experimentation.experiment.runtime import (
    ExperimentComponentBinder,
    ExperimentRuntime,
    ExperimentRuntimeComponents,
    ExperimentTrialCycleExecutor,
    trial_protocol_identity,
)
from research_platform.participant.session.runtime.checkpoint_runtime import ParticipantCheckpointRuntime
from research_platform.execution.participants import (
    ParticipantCheckpointOperations,
    ParticipantResolutionOperations,
    ParticipantSessionLifecycle,
)
from research_platform.experimentation.checkpoint.api.contracts import RunCheckpointStore
from research_platform.experimentation.checkpoint.runtime.coordination import RunCheckpointCoordinator
from research_platform.experimentation.run.runtime.decision_coordination import DecisionCycleCoordinator
from research_platform.experimentation.run.identity.api import RunIdentityProvider
from research_platform.experimentation.run.identity.providers import RandomRunIdentityProvider
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentityProvider, RandomDecisionCycleIdentityProvider
from research_platform.experimentation.run.runtime.coordination import RunCoordinator
from research_platform.experimentation.run.lifecycle.runtime import DefaultRunSessionFactory
from research_platform.experimentation.experiment.api import ExperimentTrialProtocol
from research_platform.execution.workflow.api import WorkflowSurfaceFactory
from research_platform.execution.workflow.runtime import EffectIntentOperations, KernelOperationDispatcher, WORKFLOW_RUNTIME_IDENTITY


def build_experiment_runtime_components(
    *,
    participant_adapters: tuple[ParticipantLifecycleAdapter, ...],
    trial_protocol: ExperimentTrialProtocol,
    workflow_surface_factories: tuple[WorkflowSurfaceFactory, ...],
    services: object = None,
    operation_executor: OperationExecutor | None = None,
    effect_journal: EffectIntentJournal | None = None,
    checkpoint_store: RunCheckpointStore | None = None,
) -> ExperimentRuntimeComponents:
    dispatcher = KernelOperationDispatcher(operation_executor or OperationExecutor(), caller=WORKFLOW_RUNTIME_IDENTITY)
    adapters = ParticipantLifecycleAdapterRegistry(participant_adapters)
    participant_resolution = ParticipantResolutionOperations(dispatcher, adapters)
    binder = ExperimentComponentBinder(participant_resolution)
    lifecycle = ParticipantSessionLifecycle(dispatcher, services)
    participant_checkpoints = ParticipantCheckpointOperations(dispatcher, ParticipantCheckpointRuntime())
    effect_intents = EffectIntentOperations(dispatcher, effect_journal) if effect_journal is not None else None
    trial_cycle = ExperimentTrialCycleExecutor(
        dispatcher,
        trial_protocol,
        effect_intents=effect_intents,
        workflow_surface_factories=workflow_surface_factories,
    )
    checkpoint = (
        RunCheckpointCoordinator(dispatcher, checkpoint_store, participant_checkpoints)
        if checkpoint_store is not None
        else None
    )
    return ExperimentRuntimeComponents(
        trial_protocol_identity(trial_protocol),
        DecisionCycleCoordinator(binder, lifecycle, trial_cycle),
        RunCoordinator(binder, lifecycle, trial_cycle, checkpoint, DefaultRunSessionFactory()),
    )


def build_experiment_runtime(
    *,
    participant_adapters: tuple[ParticipantLifecycleAdapter, ...],
    trial_protocol: ExperimentTrialProtocol,
    workflow_surface_factories: tuple[WorkflowSurfaceFactory, ...],
    services: object = None,
    operation_executor: OperationExecutor | None = None,
    cycle_identity_provider: DecisionCycleIdentityProvider | None = None,
    run_identity_provider: RunIdentityProvider | None = None,
    effect_journal: EffectIntentJournal | None = None,
    checkpoint_store: RunCheckpointStore | None = None,
) -> ExperimentRuntime:
    components = build_experiment_runtime_components(
        participant_adapters=participant_adapters,
        trial_protocol=trial_protocol,
        workflow_surface_factories=workflow_surface_factories,
        services=services,
        operation_executor=operation_executor,
        effect_journal=effect_journal,
        checkpoint_store=checkpoint_store,
    )
    return ExperimentRuntime(
        components,
        run_identity_provider=run_identity_provider or RandomRunIdentityProvider(),
        cycle_identity_provider=cycle_identity_provider or RandomDecisionCycleIdentityProvider(),
    )


__all__ = ["build_experiment_runtime", "build_experiment_runtime_components"]
