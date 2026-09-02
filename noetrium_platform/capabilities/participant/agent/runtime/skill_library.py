from __future__ import annotations

from dataclasses import replace
import re
from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from ..api.cognition import (
    AgentActionSequence,
    AgentGoal,
    AgentObservation,
    AgentSkillRecord,
    AgentStepReceipt,
)
from ..api.cognition_ports import AgentSkillLibraryPort
from ..api.skill_checkpoint import AgentSkillLibraryCheckpoint


def _tokens(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9_:-]+", value.lower()) if len(item) > 1}


class InMemorySkillLibrary(AgentSkillLibraryPort):
    """Structured recipe retrieval; it stores actions, never executable code."""

    def __init__(self, records: tuple[AgentSkillRecord, ...] = (), *, max_records: int = 512) -> None:
        if max_records < 1:
            raise ValueError("skill library max_records must be positive")
        self._records = list(records)
        self._max_records = max_records

    def register(self, record: AgentSkillRecord) -> None:
        self._records = [existing for existing in self._records if existing.skill_id != record.skill_id]
        self._records.append(record)
        self._records = self._records[-self._max_records :]

    def search(self, goal: AgentGoal, observation: AgentObservation, *, limit: int, context: ExecutionContext) -> tuple[AgentSkillRecord, ...]:
        del context
        if limit < 1:
            raise ValueError("skill search limit must be positive")
        query = _tokens(goal.objective + " " + " ".join(str(key) for key in observation.state))
        scored: list[tuple[float, AgentSkillRecord]] = []
        for record in self._records:
            overlap = len(query & _tokens(record.summary + " " + " ".join(record.tags)))
            reliability = (record.success_count + 1) / (record.success_count + record.failure_count + 2)
            if overlap or record.skill_id in query:
                scored.append((overlap * 10 + reliability, record))
        scored.sort(key=lambda item: (-item[0], item[1].skill_id, item[1].version))
        return tuple(record for _, record in scored[:limit])

    def record(self, sequence: AgentActionSequence, receipts: tuple[AgentStepReceipt, ...], *, success: bool, context: ExecutionContext) -> None:
        del context
        if not receipts:
            return
        existing = next((record for record in self._records if record.skill_id == sequence.skill_id), None)
        recipe = tuple((step.action_type, dict(step.payload)) for step in sequence.steps)
        if existing is None:
            self.register(AgentSkillRecord(
                skill_id=sequence.skill_id, version="1", summary=f"learned sequence for {sequence.skill_id}",
                tags=("learned",), source_refs=("agent-cognition",), recipe=recipe,
                success_count=1 if success else 0, failure_count=0 if success else 1,
            ))
            return
        self.register(replace(
            existing,
            recipe=recipe,
            success_count=existing.success_count + (1 if success else 0),
            failure_count=existing.failure_count + (0 if success else 1),
        ))

    def snapshot(self) -> tuple[AgentSkillRecord, ...]:
        return tuple(self._records)

    def checkpoint(self) -> AgentSkillLibraryCheckpoint:
        return AgentSkillLibraryCheckpoint(records=tuple(self._records))

    def restore(self, checkpoint: AgentSkillLibraryCheckpoint) -> None:
        if not isinstance(checkpoint, AgentSkillLibraryCheckpoint):
            raise TypeError("checkpoint must be an AgentSkillLibraryCheckpoint")
        if len(checkpoint.records) > self._max_records:
            raise ValueError("agent skill library checkpoint exceeds configured record capacity")
        self._records = list(checkpoint.records)


__all__ = ["InMemorySkillLibrary"]
