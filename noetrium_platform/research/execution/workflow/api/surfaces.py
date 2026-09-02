from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from noetrium_platform.capabilities.participant.core.api import BoundParticipants, ParticipantSessionBinding

from .dispatch import OperationDispatchPort
from .effect_intents import EffectIntentOperationPort


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceBindingContext:
    dispatcher: OperationDispatchPort
    bound: BoundParticipants
    participant_sessions: tuple[ParticipantSessionBinding, ...]
    effect_intents: EffectIntentOperationPort | None = None


@runtime_checkable
class WorkflowSurfaceFactory(Protocol):
    surface_id: str

    def bind(self, context: WorkflowSurfaceBindingContext) -> object: ...


def workflow_surface_id(workflow: object) -> str:
    value = getattr(workflow, "surface_id", None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("workflow must declare a non-empty surface_id")
    return value


__all__ = [
    "WorkflowSurfaceBindingContext",
    "WorkflowSurfaceFactory",
    "workflow_surface_id",
]
