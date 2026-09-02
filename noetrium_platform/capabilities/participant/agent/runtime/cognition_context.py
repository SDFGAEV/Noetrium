from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from ..api.cognition import (
    AgentCognitionError,
    AgentGoal,
    AgentMemoryContext,
    AgentObservation,
    AgentSkillRecord,
)
from ..api.cognition_ports import AgentMemoryPort, AgentSkillLibraryPort


FailureSink = Callable[..., None]


@dataclass(frozen=True, slots=True)
class CognitionContextSnapshot:
    memory: AgentMemoryContext
    retrieved_skills: tuple[AgentSkillRecord, ...]


class CognitionContextPhase:
    """Own verified-memory and durable-skill context retrieval for one reasoning call."""

    def __init__(
        self,
        *,
        memory: AgentMemoryPort,
        skill_library: AgentSkillLibraryPort | None,
        failure: FailureSink,
    ) -> None:
        self._memory = memory
        self._skill_library = skill_library
        self._failure = failure

    def gather(
        self,
        *,
        goal: AgentGoal,
        observation: AgentObservation,
        context: ExecutionContext,
    ) -> CognitionContextSnapshot:
        try:
            memory = self._memory.recall(goal, observation, context)
            if not isinstance(memory, AgentMemoryContext):
                raise TypeError("agent memory port returned an invalid context")
            retrieved_skills: tuple[AgentSkillRecord, ...] = ()
            if self._skill_library is not None:
                retrieved_skills = self._skill_library.search(
                    goal, observation, limit=8, context=context
                )
                if not isinstance(retrieved_skills, tuple) or any(
                    not isinstance(item, AgentSkillRecord) for item in retrieved_skills
                ):
                    raise TypeError("agent skill library returned an invalid result")
            return CognitionContextSnapshot(memory, retrieved_skills)
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_CONTEXT_FAILED", str(exc), phase="context")
            raise AgentCognitionError(
                "context", "AGENT_CONTEXT_FAILED", str(exc), cause=exc
            ) from exc


__all__ = ["CognitionContextPhase", "CognitionContextSnapshot"]
