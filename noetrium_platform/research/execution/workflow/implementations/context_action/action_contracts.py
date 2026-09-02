from __future__ import annotations

from dataclasses import dataclass

from noetrium_platform.infrastructure.reliability.effect.api import EffectIntent
from noetrium_platform.capabilities.environment.runtime.api import ActionRequest, ActionResult
from noetrium_platform.foundation.kernel.kernel import JsonValue, OperationResult


@dataclass(frozen=True, slots=True)
class SafeActionExecution:
    result: ActionResult
    operation_results: tuple[OperationResult[JsonValue], ...]
    replayed_from_intent: bool = False


@dataclass(frozen=True, slots=True)
class ActionSafetyPermit:
    decision_cycle_id: str
    environment_component_digest: str
    journal_durability: str | None
    request_digest: str
    intent_id: str | None


@dataclass(frozen=True, slots=True)
class PreparedSafeAction:
    """Exact action authorization frozen before crossing the side-effect boundary."""

    request: ActionRequest
    intent: EffectIntent | None
    permit: ActionSafetyPermit
    operation_results: tuple[OperationResult[JsonValue], ...] = ()


__all__ = ["ActionSafetyPermit", "PreparedSafeAction", "SafeActionExecution"]
