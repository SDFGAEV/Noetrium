from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Callable

from ..api.cognition import AgentGoal, AgentObservation


class SelfPrompterLifecycle(StrEnum):
    STOPPED = "stopped"
    ACTIVE = "active"
    PAUSED = "paused"


@dataclass(frozen=True, slots=True)
class SelfPrompterState:
    schema_version: str
    lifecycle: SelfPrompterLifecycle
    goal_id: str
    prompt_count: int
    no_command_count: int
    next_prompt_at: float
    pause_reason: str

    def __post_init__(self) -> None:
        if self.schema_version != "agent-self-prompter.v1":
            raise ValueError("unsupported self-prompter snapshot")
        if (
            type(self.prompt_count) is not int
            or self.prompt_count < 0
            or type(self.no_command_count) is not int
            or self.no_command_count < 0
        ):
            raise ValueError("self-prompter counters cannot be negative")
        if (
            isinstance(self.next_prompt_at, bool)
            or not isinstance(self.next_prompt_at, (int, float))
            or not math.isfinite(float(self.next_prompt_at))
        ):
            raise ValueError("self-prompter next_prompt_at must be finite")


@dataclass(frozen=True, slots=True)
class SelfPromptEvent:
    kind: str
    goal_id: str
    text: str = ""
    reason: str = ""


class AgentSelfPrompter:
    """Persistent-goal driver with cooldown and no-command watchdog.

    It emits prompt events but does not call a model or execute an action.  A
    model-backed planner can consume the event through the platform's normal
    typed request path, keeping autonomous prompting auditable.
    """

    def __init__(
        self,
        goal: AgentGoal,
        *,
        prompt_factory: Callable[[AgentGoal, AgentObservation | None], str],
        clock: Callable[[], float],
        cooldown_s: float = 2.0,
        no_command_limit: int = 3,
    ) -> None:
        if (
            isinstance(cooldown_s, bool)
            or not isinstance(cooldown_s, (int, float))
            or not math.isfinite(float(cooldown_s))
            or cooldown_s < 0
            or type(no_command_limit) is not int
            or no_command_limit < 1
        ):
            raise ValueError("self-prompter limits are invalid")
        self.goal = goal
        self._prompt_factory = prompt_factory
        self._clock = clock
        self._cooldown_s = cooldown_s
        self._no_command_limit = no_command_limit
        self._lifecycle = SelfPrompterLifecycle.STOPPED
        self._prompt_count = 0
        self._no_command_count = 0
        self._next_prompt_at = 0.0
        self._pause_reason = ""

    @property
    def lifecycle(self) -> SelfPrompterLifecycle:
        return self._lifecycle

    def start(self) -> SelfPromptEvent:
        self._lifecycle = SelfPrompterLifecycle.ACTIVE
        self._pause_reason = ""
        self._next_prompt_at = self._clock()
        return SelfPromptEvent("started", self.goal.goal_id)

    def stop(self, reason: str = "stopped") -> SelfPromptEvent:
        self._lifecycle = SelfPrompterLifecycle.STOPPED
        self._pause_reason = reason
        return SelfPromptEvent("stopped", self.goal.goal_id, reason=reason)

    def pause(self, reason: str) -> SelfPromptEvent:
        if not reason.strip():
            raise ValueError("pause reason is required")
        self._lifecycle = SelfPrompterLifecycle.PAUSED
        self._pause_reason = reason.strip()
        return SelfPromptEvent("paused", self.goal.goal_id, reason=self._pause_reason)

    def resume(self) -> SelfPromptEvent:
        self._lifecycle = SelfPrompterLifecycle.ACTIVE
        self._pause_reason = ""
        self._next_prompt_at = self._clock()
        return SelfPromptEvent("resumed", self.goal.goal_id)

    def notify_command(self, *, accepted: bool) -> None:
        self._no_command_count = 0 if accepted else self._no_command_count + 1
        self._next_prompt_at = self._clock() + self._cooldown_s

    def notify_user_message(self) -> SelfPromptEvent:
        return self.pause("user_conversation")

    def tick(self, observation: AgentObservation | None = None) -> SelfPromptEvent | None:
        if self._lifecycle is not SelfPrompterLifecycle.ACTIVE or self._clock() < self._next_prompt_at:
            return None
        text = self._prompt_factory(self.goal, observation).strip()
        if not text:
            self._no_command_count += 1
            if self._no_command_count >= self._no_command_limit:
                return self.pause("no_command_watchdog")
            self._next_prompt_at = self._clock() + self._cooldown_s
            return SelfPromptEvent("empty_prompt", self.goal.goal_id, reason="planner_emitted_no_command")
        self._prompt_count += 1
        self._no_command_count = 0
        self._next_prompt_at = self._clock() + self._cooldown_s
        return SelfPromptEvent("prompt", self.goal.goal_id, text=text)

    def snapshot(self) -> SelfPrompterState:
        return SelfPrompterState(
            schema_version="agent-self-prompter.v1",
            lifecycle=self._lifecycle,
            goal_id=self.goal.goal_id,
            prompt_count=self._prompt_count,
            no_command_count=self._no_command_count,
            next_prompt_at=self._next_prompt_at,
            pause_reason=self._pause_reason,
        )

    def restore(self, snapshot: SelfPrompterState) -> None:
        if snapshot.goal_id != self.goal.goal_id:
            raise ValueError("self-prompter snapshot belongs to another goal")
        self._lifecycle = snapshot.lifecycle
        self._prompt_count = snapshot.prompt_count
        self._no_command_count = snapshot.no_command_count
        self._next_prompt_at = snapshot.next_prompt_at
        self._pause_reason = snapshot.pause_reason


__all__ = [
    "AgentSelfPrompter",
    "SelfPromptEvent",
    "SelfPrompterLifecycle",
    "SelfPrompterState",
]
