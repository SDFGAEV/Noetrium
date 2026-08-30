from __future__ import annotations

import pytest

from research_platform.participant.agent.api import (
    AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA,
    AgentSkillLibraryCheckpoint,
    AgentSkillRecord,
)
from research_platform.participant.agent.runtime import InMemorySkillLibrary


def _record(skill_id: str, *, success: int = 1) -> AgentSkillRecord:
    return AgentSkillRecord(
        skill_id=skill_id,
        version="1",
        summary=f"learned {skill_id}",
        tags=("learned",),
        source_refs=("test",),
        recipe=(("move", {"target": {"x": 1, "y": 2}, "path": [1, 2, 3]}),),
        success_count=success,
        failure_count=0,
    )


def test_skill_checkpoint_round_trip_preserves_recipe_and_counters() -> None:
    source = InMemorySkillLibrary((_record("skill.move", success=3),))
    encoded = source.checkpoint().to_dict()
    assert encoded["schema_version"] == AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA
    restored_checkpoint = AgentSkillLibraryCheckpoint.from_dict(encoded)
    target = InMemorySkillLibrary()
    target.restore(restored_checkpoint)

    assert target.snapshot() == source.snapshot()
    restored_record = target.snapshot()[0]
    assert restored_record.success_count == 3
    assert restored_record.recipe[0][1]["path"] == (1, 2, 3)


def test_skill_checkpoint_decode_rejects_coercion_and_unknown_fields() -> None:
    document = InMemorySkillLibrary((_record("skill.move"),)).checkpoint().to_dict()
    document["records"][0]["success_count"] = True
    with pytest.raises(ValueError, match="success_count"):
        AgentSkillLibraryCheckpoint.from_dict(document)

    document = InMemorySkillLibrary((_record("skill.move"),)).checkpoint().to_dict()
    document["records"][0]["unexpected"] = "value"
    with pytest.raises(ValueError, match="fields mismatch"):
        AgentSkillLibraryCheckpoint.from_dict(document)


def test_skill_restore_rejects_capacity_mismatch_without_mutation() -> None:
    target = InMemorySkillLibrary((_record("skill.keep"),), max_records=1)
    checkpoint = AgentSkillLibraryCheckpoint(records=(
        _record("skill.one"),
        _record("skill.two"),
    ))
    before = target.snapshot()

    with pytest.raises(ValueError, match="capacity"):
        target.restore(checkpoint)

    assert target.snapshot() == before


def test_skill_record_rejects_non_finite_recipe_values_before_checkpoint() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        AgentSkillRecord(
            skill_id="skill.bad",
            version="1",
            summary="bad recipe",
            recipe=(("move", {"distance": float("nan")}),),
        )
