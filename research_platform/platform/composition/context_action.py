from __future__ import annotations

from research_platform.platform.composition.experiment_runtime import build_experiment_runtime
from research_platform.platform.composition.operation_forensics import CoreOperationFailureClassifier, OperationFailureClassifierChain
from research_platform.platform.composition.participants.environment import environment_participant_adapter
from research_platform.platform.composition.participants.method import method_participant_adapter
from research_platform.reliability.effect.api import EffectIntentJournal
from research_platform.platform.kernel import OperationExecutor
from research_platform.participant.core.api.runtime import ParticipantResolverPort
from research_platform.experimentation.experiment.runtime import ExperimentRuntime
from research_platform.experimentation.checkpoint import RunCheckpointStore
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentityProvider
from research_platform.participant.core.api.lifecycle import ParticipantLifecycleAdapter
from research_platform.execution.workflow.api import WorkflowSurfaceFactory
from research_platform.execution.workflow.implementations.context_action import ContextActionTrialProtocol, ContextActionSurfaceFactory
from research_platform.execution.workflow.implementations.context_action.failure_classifier import ContextActionFailureClassifier


def context_action_participant_adapters(
    resolver: ParticipantResolverPort,
    *,
    extra: tuple[ParticipantLifecycleAdapter, ...] = (),
) -> tuple[ParticipantLifecycleAdapter, ...]:
    return (method_participant_adapter(resolver), environment_participant_adapter(resolver), *extra)


def context_action_failure_classifier_chain() -> OperationFailureClassifierChain:
    return OperationFailureClassifierChain((ContextActionFailureClassifier(), CoreOperationFailureClassifier()))


def compose_context_action_runtime(
    resolver: ParticipantResolverPort,
    *,
    services: object = None,
    operation_executor: OperationExecutor | None = None,
    cycle_identity_provider: DecisionCycleIdentityProvider | None = None,
    effect_journal: EffectIntentJournal | None = None,
    checkpoint_store: RunCheckpointStore | None = None,
    extra_participant_adapters: tuple[ParticipantLifecycleAdapter, ...] = (),
    extra_surface_factories: tuple[WorkflowSurfaceFactory, ...] = (),
) -> ExperimentRuntime:
    return build_experiment_runtime(
        participant_adapters=context_action_participant_adapters(resolver, extra=extra_participant_adapters),
        trial_protocol=ContextActionTrialProtocol(),
        workflow_surface_factories=(ContextActionSurfaceFactory(), *extra_surface_factories),
        services=services,
        operation_executor=operation_executor,
        cycle_identity_provider=cycle_identity_provider,
        effect_journal=effect_journal,
        checkpoint_store=checkpoint_store,
    )


__all__ = [
    "compose_context_action_runtime",
    "context_action_failure_classifier_chain",
    "context_action_participant_adapters",
]
