from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping

from noetrium_platform.foundation.kernel.kernel import canonical_digest, freeze_json

from ..api.cognition import AgentGoal, JsonValue


class GoalStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AgentSubgoal:
    goal_id: str
    objective: str
    dependencies: tuple[str, ...] = ()
    priority: int = 0
    context: Mapping[str, JsonValue] = field(default_factory=dict)
    status: GoalStatus = GoalStatus.PENDING
    attempts: int = 0

    def __post_init__(self) -> None:
        if not self.goal_id.strip() or not self.objective.strip() or self.priority < 0 or self.attempts < 0:
            raise ValueError("agent subgoal is invalid")
        if len(set(self.dependencies)) != len(self.dependencies) or self.goal_id in self.dependencies:
            raise ValueError("agent subgoal dependencies are invalid")
        if not isinstance(self.context, Mapping):
            raise TypeError("agent subgoal context must be a mapping")
        object.__setattr__(
            self, "context", freeze_json(self.context)
        )

    def as_goal(self, *, max_steps: int = 32, max_seconds: float = 300.0) -> AgentGoal:
        return AgentGoal(self.goal_id, self.objective, dict(self.context), max_steps=max_steps, max_seconds=max_seconds)


class AgentGoalGraph:
    """Durable DAG scheduler for long-horizon decomposition and recovery."""

    def __init__(self, goals: tuple[AgentSubgoal, ...] = ()) -> None:
        self._goals: dict[str, AgentSubgoal] = {}
        for goal in goals:
            self.add(goal)

    def add(self, goal: AgentSubgoal) -> None:
        if goal.goal_id in self._goals:
            raise ValueError(f"duplicate agent goal: {goal.goal_id}")
        self._goals[goal.goal_id] = goal
        try:
            self._validate()
        except BaseException:
            del self._goals[goal.goal_id]
            raise

    def _validate(self) -> None:
        for goal in self._goals.values():
            if any(dependency not in self._goals for dependency in goal.dependencies):
                raise ValueError(f"unknown goal dependency for {goal.goal_id}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(goal_id: str) -> None:
            if goal_id in visiting:
                raise ValueError("agent goal graph contains a cycle")
            if goal_id in visited:
                return
            visiting.add(goal_id)
            for dependency in self._goals[goal_id].dependencies:
                visit(dependency)
            visiting.remove(goal_id)
            visited.add(goal_id)

        for goal_id in self._goals:
            visit(goal_id)

    def ready(self) -> tuple[AgentSubgoal, ...]:
        completed = {goal_id for goal_id, goal in self._goals.items() if goal.status is GoalStatus.COMPLETED}
        return tuple(
            sorted(
                (
                    goal for goal in self._goals.values()
                    if goal.status is GoalStatus.PENDING and all(dependency in completed for dependency in goal.dependencies)
                ),
                key=lambda goal: (-goal.priority, goal.goal_id),
            )
        )

    def activate(self, goal_id: str) -> AgentSubgoal:
        goal = self._require(goal_id)
        if goal not in self.ready():
            raise ValueError(f"goal is not ready: {goal_id}")
        updated = replace(goal, status=GoalStatus.ACTIVE, attempts=goal.attempts + 1)
        self._goals[goal_id] = updated
        return updated

    def complete(self, goal_id: str) -> AgentSubgoal:
        goal = self._require(goal_id)
        if goal.status is not GoalStatus.ACTIVE:
            raise ValueError("only active goals can complete")
        updated = replace(goal, status=GoalStatus.COMPLETED)
        self._goals[goal_id] = updated
        return updated

    def fail(self, goal_id: str, *, blocked: bool = False) -> AgentSubgoal:
        goal = self._require(goal_id)
        updated = replace(goal, status=GoalStatus.BLOCKED if blocked else GoalStatus.FAILED)
        self._goals[goal_id] = updated
        return updated

    def _require(self, goal_id: str) -> AgentSubgoal:
        try:
            return self._goals[goal_id]
        except KeyError as exc:
            raise KeyError(f"unknown agent goal: {goal_id}") from exc

    def get(self, goal_id: str) -> AgentSubgoal:
        return self._require(goal_id)

    def snapshot(self) -> tuple[AgentSubgoal, ...]:
        return tuple(self._goals.values())

    @property
    def digest(self) -> str:
        return canonical_digest([
            {"goal_id": goal.goal_id, "objective": goal.objective, "dependencies": goal.dependencies, "priority": goal.priority, "status": goal.status.value, "attempts": goal.attempts}
            for goal in self._goals.values()
        ])


__all__ = ["AgentGoalGraph", "AgentSubgoal", "GoalStatus"]
