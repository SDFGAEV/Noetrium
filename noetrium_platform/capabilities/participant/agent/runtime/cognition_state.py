from __future__ import annotations

from dataclasses import dataclass, replace

from ..api.cognition import AgentLoopCheckpoint


@dataclass(frozen=True, slots=True)
class CognitionCounters:
    step: int = 0
    plan_calls: int = 0
    no_progress_steps: int = 0
    same_action_runs: int = 0

    @classmethod
    def from_checkpoint(cls, checkpoint: AgentLoopCheckpoint | None) -> "CognitionCounters":
        if checkpoint is None:
            return cls()
        return cls(
            step=checkpoint.step,
            plan_calls=checkpoint.plan_calls,
            no_progress_steps=checkpoint.no_progress_steps,
            same_action_runs=checkpoint.same_action_runs,
        )

    def with_plan_calls(self, value: int) -> "CognitionCounters":
        if value < self.plan_calls:
            raise ValueError("cognition plan call counter cannot move backwards")
        return replace(self, plan_calls=value)

    def after_action(self, *, progressed: bool, repeated_action: bool) -> "CognitionCounters":
        return replace(
            self,
            step=self.step + 1,
            no_progress_steps=0 if progressed else self.no_progress_steps + 1,
            same_action_runs=self.same_action_runs + 1 if repeated_action else 1,
        )


__all__ = ["CognitionCounters"]
