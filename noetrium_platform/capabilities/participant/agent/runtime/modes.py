from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from ..api.cognition import (
    AgentActionSequence,
    AgentGoal,
    AgentModeDecision,
    AgentModeDisposition,
    AgentObservation,
    AgentSkillSelection,
)
from ..api.cognition_ports import AgentReactiveModePort


@dataclass(frozen=True, slots=True)
class ReactiveModeSpec:
    mode_id: str
    priority: int
    description: str
    trigger: Callable[[AgentObservation], bool]
    disposition: AgentModeDisposition = AgentModeDisposition.REPLAN
    replacement: AgentActionSequence | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.mode_id.strip() or not self.description.strip() or self.priority < 0:
            raise ValueError("reactive mode specification is invalid")
        if self.disposition is AgentModeDisposition.PREEMPT and self.replacement is None:
            raise ValueError("preempting mode requires a replacement sequence")


class ReactiveModeController(AgentReactiveModePort):
    """Priority-ordered safety and self-preservation modes."""

    def __init__(self, modes: tuple[ReactiveModeSpec, ...] = ()) -> None:
        self._modes: dict[str, ReactiveModeSpec] = {}
        for mode in modes:
            self.register(mode)

    def register(self, mode: ReactiveModeSpec) -> None:
        if mode.mode_id in self._modes:
            raise ValueError(f"duplicate reactive mode: {mode.mode_id}")
        self._modes[mode.mode_id] = mode

    def set_enabled(self, mode_id: str, enabled: bool) -> None:
        try:
            mode = self._modes[mode_id]
        except KeyError as exc:
            raise KeyError(f"unknown reactive mode: {mode_id}") from exc
        self._modes[mode_id] = ReactiveModeSpec(
            mode_id=mode.mode_id, priority=mode.priority, description=mode.description,
            trigger=mode.trigger, disposition=mode.disposition, replacement=mode.replacement, enabled=enabled,
        )

    def review(self, goal: AgentGoal, observation: AgentObservation, selection: AgentSkillSelection, sequence: AgentActionSequence, context: ExecutionContext) -> AgentModeDecision | None:
        del goal, selection, sequence, context
        for mode in sorted(self._modes.values(), key=lambda item: (-item.priority, item.mode_id)):
            if not mode.enabled:
                continue
            try:
                active = mode.trigger(observation)
            except BaseException as exc:
                raise RuntimeError(f"reactive mode {mode.mode_id} trigger failed") from exc
            if active:
                return AgentModeDecision(mode.mode_id, mode.disposition, mode.description, mode.replacement)
        return None

    def enabled_modes(self) -> tuple[str, ...]:
        return tuple(mode.mode_id for mode in sorted(self._modes.values(), key=lambda item: (-item.priority, item.mode_id)) if mode.enabled)


__all__ = ["ReactiveModeController", "ReactiveModeSpec"]
