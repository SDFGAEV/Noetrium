from __future__ import annotations

from research_platform.platform.composition.experiment_runtime import build_experiment_runtime
from research_platform.platform.composition.operation_forensics import CoreOperationFailureClassifier, OperationFailureClassifierChain
from research_platform.platform.composition.participants.agent import agent_participant_adapter
from research_platform.platform.composition.participants.capability import capability_participant_adapter
from research_platform.platform.composition.participants.generic import generic_participant_adapter
from research_platform.reliability.effect.api import EffectIntentJournal
from research_platform.platform.kernel import OperationExecutor
from research_platform.participant.core.api.runtime import ParticipantResolverPort
from research_platform.experimentation.experiment.runtime import ExperimentRuntime
from research_platform.experimentation.checkpoint import RunCheckpointStore
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentityProvider
from research_platform.participant.core.api.lifecycle import ParticipantLifecycleAdapter
from research_platform.execution.workflow.api import WorkflowSurfaceFactory
from research_platform.execution.workflow.implementations.agent_turn import AgentTurnTrialProtocol, AgentTurnSurfaceFactory
from research_platform.execution.workflow.implementations.agent_turn.failure_classifier import AgentTurnFailureClassifier
from research_platform.execution.capability.runtime import (
    CapabilityInvocationPipelineFactory,
    ScopedRegistrationRuntimeFactory,
)


def agent_turn_participant_adapters(
    resolver: ParticipantResolverPort,
    *,
    runtime_kinds: tuple[str, ...] = (),
    include_capability_provider: bool = True,
    extra: tuple[ParticipantLifecycleAdapter, ...] = (),
) -> tuple[ParticipantLifecycleAdapter, ...]:
    rows: list[ParticipantLifecycleAdapter] = [agent_participant_adapter(resolver)]
    if include_capability_provider:
        rows.append(capability_participant_adapter(resolver))
    rows.extend(generic_participant_adapter(kind, resolver) for kind in runtime_kinds)
    rows.extend(extra)
    return tuple(rows)


def agent_turn_failure_classifier_chain() -> OperationFailureClassifierChain:
    return OperationFailureClassifierChain((AgentTurnFailureClassifier(), CoreOperationFailureClassifier()))


def compose_agent_turn_runtime(
    resolver: ParticipantResolverPort,
    *,
    runtime_kinds: tuple[str, ...] = (),
    include_capability_provider: bool = True,
    services: object = None,
    operation_executor: OperationExecutor | None = None,
    cycle_identity_provider: DecisionCycleIdentityProvider | None = None,
    effect_journal: EffectIntentJournal | None = None,
    checkpoint_store: RunCheckpointStore | None = None,
    extra_participant_adapters: tuple[ParticipantLifecycleAdapter, ...] = (),
    extra_surface_factories: tuple[WorkflowSurfaceFactory, ...] = (),
) -> ExperimentRuntime:
    return build_experiment_runtime(
        participant_adapters=agent_turn_participant_adapters(
            resolver,
            runtime_kinds=runtime_kinds,
            include_capability_provider=include_capability_provider,
            extra=extra_participant_adapters,
        ),
        trial_protocol=AgentTurnTrialProtocol(),
        workflow_surface_factories=(
            AgentTurnSurfaceFactory(
                CapabilityInvocationPipelineFactory(),
                ScopedRegistrationRuntimeFactory(),
            ),
            *extra_surface_factories,
        ),
        services=services,
        operation_executor=operation_executor,
        cycle_identity_provider=cycle_identity_provider,
        effect_journal=effect_journal,
        checkpoint_store=checkpoint_store,
    )


__all__ = [
    "agent_turn_failure_classifier_chain",
    "agent_turn_participant_adapters",
    "compose_agent_turn_runtime",
]
