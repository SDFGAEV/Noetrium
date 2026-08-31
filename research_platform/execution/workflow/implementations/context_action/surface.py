from __future__ import annotations

from research_platform.execution.workflow.api import WorkflowSurfaceBindingContext

from .context_action_operations import ContextActionTrialOperations


class ContextActionSurfaceFactory:
    surface_id = "context_action.operations.v1"

    @staticmethod
    def bind(context: WorkflowSurfaceBindingContext) -> ContextActionTrialOperations:
        return ContextActionTrialOperations(
            context.dispatcher,
            context.bound,
            context.participant_sessions,
            effect_intents=context.effect_intents,
        )


__all__ = ["ContextActionSurfaceFactory"]
