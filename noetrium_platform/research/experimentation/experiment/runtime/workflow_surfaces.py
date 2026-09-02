from __future__ import annotations

from noetrium_platform.research.execution.workflow.api import (
    WorkflowSurfaceBindingContext,
    WorkflowSurfaceFactory,
    workflow_surface_id,
)


class ExperimentWorkflowSurfaceRegistry:
    """Study-owned selection registry; surface contracts themselves are workflow-generic."""

    def __init__(self, factories: tuple[WorkflowSurfaceFactory, ...]) -> None:
        self._factories = {factory.surface_id: factory for factory in factories}
        if len(self._factories) != len(factories):
            raise ValueError("duplicate workflow surface_id")

    def bind(self, surface_id: str, context: WorkflowSurfaceBindingContext) -> object:
        try:
            factory = self._factories[surface_id]
        except KeyError as exc:
            raise LookupError(f"no workflow surface factory for surface_id={surface_id!r}") from exc
        return factory.bind(context)


__all__ = ["ExperimentWorkflowSurfaceRegistry"]
