"""Reusable single-agent paper-method control loops.

The implementations deliberately leave model prompting and domain actions to
injected downstream ports. A paper can replace one policy or the whole loop.
"""

from __future__ import annotations

from .contracts import (
    ReferenceAgentActionKind,
    ReferenceAgentDecisionPort,
    ReferenceAgentMessage,
    ReferenceAgentReflectionPort,
    ReferenceAgentRunResult,
    ReferenceAgentSolverPort,
    ReferenceAgentState,
    ReferenceAgentStatus,
    ReferenceAgentToolPort,
    ReferenceAgentPlannerPort,
)


class ReferenceReActMethod:
    """Reason/action/observation loop with an explicit step budget."""

    def __init__(self, policy: ReferenceAgentDecisionPort, tools: ReferenceAgentToolPort) -> None:
        self._policy = policy
        self._tools = tools

    def run(self, task: str, *, max_steps: int = 16) -> ReferenceAgentRunResult:
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("ReAct max_steps must be positive")
        state = ReferenceAgentState(task, messages=(ReferenceAgentMessage("user", task),))
        for _ in range(max_steps):
            decision = self._policy.decide(state)
            action = decision.action
            reasoning = decision.reasoning or action.content
            messages = state.messages + (ReferenceAgentMessage("assistant", reasoning),)
            if action.kind is ReferenceAgentActionKind.FINAL:
                final_state = ReferenceAgentState(task, messages=messages, scratchpad=state.scratchpad, step=state.step + 1)
                return ReferenceAgentRunResult(ReferenceAgentStatus.COMPLETED, action.content, final_state)
            if action.kind is ReferenceAgentActionKind.TOOL:
                observation = self._tools.invoke(action.name, action.arguments)
                scratchpad = state.scratchpad + (
                    ReferenceAgentMessage("assistant", action.content or action.name),
                    ReferenceAgentMessage("tool", observation.content, action.name),
                )
                state = ReferenceAgentState(task, messages=messages, scratchpad=scratchpad, step=state.step + 1)
                continue
            if action.kind is ReferenceAgentActionKind.CONTINUE:
                state = ReferenceAgentState(
                    task,
                    messages=messages,
                    scratchpad=state.scratchpad + (ReferenceAgentMessage("assistant", action.content),),
                    step=state.step + 1,
                )
                continue
            raise RuntimeError("unsupported ReAct action kind")
        return ReferenceAgentRunResult(
            ReferenceAgentStatus.MAX_STEPS,
            None,
            state,
            error=f"ReAct reached max_steps={max_steps}",
        )


class ReferenceReflexionMethod:
    """Re-run a bounded base method after an injected reflection."""

    def __init__(
        self,
        base: ReferenceReActMethod,
        reflector: ReferenceAgentReflectionPort,
        *,
        max_attempts: int = 2,
    ) -> None:
        if type(max_attempts) is not int or max_attempts <= 0:
            raise ValueError("Reflexion max_attempts must be positive")
        self._base = base
        self._reflector = reflector
        self._max_attempts = max_attempts

    def run(self, task: str, *, max_steps: int = 16) -> ReferenceAgentRunResult:
        latest = self._base.run(task, max_steps=max_steps)
        for _ in range(1, self._max_attempts):
            if latest.status is ReferenceAgentStatus.COMPLETED:
                return latest
            reflection = self._reflector.reflect(latest.state, latest)
            reflected_task = f"{task}\\nReflection:\\n{reflection.content}"
            latest = self._base.run(reflected_task, max_steps=max_steps)
        return latest


class ReferencePlanAndSolveMethod:
    """Two-phase planning/solving method with a replaceable solver."""

    def __init__(self, planner: ReferenceAgentPlannerPort, solver: ReferenceAgentSolverPort) -> None:
        self._planner = planner
        self._solver = solver

    def run(self, task: str) -> ReferenceAgentRunResult:
        plan = self._planner.plan(task)
        if type(plan) is not tuple or not plan or any(type(step) is not str or not step.strip() for step in plan):
            raise ValueError("Plan-and-Solve planner must return non-empty string steps")
        return self._solver.solve(task, plan)


__all__ = ["ReferencePlanAndSolveMethod", "ReferenceReActMethod", "ReferenceReflexionMethod"]
