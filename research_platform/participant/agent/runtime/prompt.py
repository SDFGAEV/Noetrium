from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable, Mapping

from research_platform.platform.kernel import canonical_bytes

from ..api.cognition import AgentGoal, AgentMemoryContext, AgentObservation, AgentSkillDescription, JsonValue


@dataclass(frozen=True, slots=True)
class PromptBlock:
    block_id: str
    text: str
    priority: int = 0
    required: bool = False

    def __post_init__(self) -> None:
        if not self.block_id.strip() or not self.text.strip():
            raise ValueError("prompt block identity and text are required")


@dataclass(frozen=True, slots=True)
class CompiledAgentPrompt:
    schema_version: str
    text: str
    block_ids: tuple[str, ...]
    truncated: bool


class AgentPromptAssembler:
    """Context-budgeted structured prompt compiler with stable block order."""

    def __init__(self, *, max_chars: int = 12000) -> None:
        if max_chars < 512:
            raise ValueError("agent prompt budget is too small")
        self._max_chars = max_chars

    def compile(
        self,
        *,
        goal: AgentGoal,
        observation: AgentObservation,
        memory: AgentMemoryContext,
        skills: Iterable[AgentSkillDescription],
        prior_actions: Iterable[Mapping[str, JsonValue]] = (),
        extra: Iterable[PromptBlock] = (),
    ) -> CompiledAgentPrompt:
        blocks = [
            PromptBlock("system", "Choose one typed skill and never claim completion without state evidence.", 100, True),
            PromptBlock("goal", json.dumps(json.loads(canonical_bytes({"goal_id": goal.goal_id, "objective": goal.objective, "context": goal.context})), sort_keys=True), 90, True),
            PromptBlock("observation", json.dumps(json.loads(canonical_bytes(observation.state)), ensure_ascii=False, sort_keys=True), 80, True),
            PromptBlock("skills", json.dumps([{"skill_id": skill.skill_id, "category": skill.category, "description": skill.description, "arguments": skill.argument_contract} for skill in skills], ensure_ascii=False, sort_keys=True), 70, True),
            PromptBlock("memory", memory.context_text or "(no verified memory)", 50),
            PromptBlock("prior_actions", json.dumps(json.loads(canonical_bytes(tuple(prior_actions))), ensure_ascii=False, sort_keys=True), 40),
            *tuple(extra),
        ]
        selected: list[PromptBlock] = []
        used = 0
        for block in sorted(blocks, key=lambda item: (-item.priority, item.block_id)):
            encoded = f"\n[{block.block_id}]\n{block.text}\n"
            if used + len(encoded) <= self._max_chars or block.required:
                selected.append(block)
                used += len(encoded)
        text = "".join(f"\n[{block.block_id}]\n{block.text}\n" for block in selected)
        if len(text) > self._max_chars:
            required_text = "".join(f"\n[{block.block_id}]\n{block.text}\n" for block in selected if block.required)
            text = required_text[: self._max_chars]
        return CompiledAgentPrompt("agent-prompt.v1", text, tuple(block.block_id for block in selected), len(selected) != len(blocks))


__all__ = ["AgentPromptAssembler", "CompiledAgentPrompt", "PromptBlock"]
