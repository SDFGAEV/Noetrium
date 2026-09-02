from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from .cognition import AgentSkillRecord, JsonValue


AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA = "agent-skill-library.v2"
_RECORD_FIELDS = frozenset({
    "skill_id", "version", "summary", "tags", "source_refs", "recipe",
    "success_count", "failure_count",
})
_RECIPE_FIELDS = frozenset({"action_type", "payload"})
_CHECKPOINT_FIELDS = frozenset({"schema_version", "records"})


def _exact(document: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(document)
    if actual != expected:
        raise ValueError(f"{label} fields mismatch: expected={sorted(expected)!r} actual={sorted(actual)!r}")


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a sequence of strings")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise ValueError(f"{field} must contain only strings")
    return result


def _json_value(value: Any, *, field: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} contains a non-finite float")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item, field=field) for item in value]
    if isinstance(value, Mapping):
        copied: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field} mapping keys must be strings")
            copied[key] = _json_value(item, field=field)
        return copied
    raise ValueError(f"{field} contains unsupported JSON value {type(value).__name__}")


def _payload(value: Any) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError("recipe payload must be a mapping")
    copied = _json_value(value, field="recipe payload")
    if not isinstance(copied, dict):
        raise ValueError("recipe payload must decode to an object")
    return copied


def _record_to_dict(record: AgentSkillRecord) -> dict[str, Any]:
    return {
        "skill_id": record.skill_id,
        "version": record.version,
        "summary": record.summary,
        "tags": list(record.tags),
        "source_refs": list(record.source_refs),
        "recipe": [
            {"action_type": action_type, "payload": _payload(payload)}
            for action_type, payload in record.recipe
        ],
        "success_count": record.success_count,
        "failure_count": record.failure_count,
    }


def _record_from_dict(document: Mapping[str, Any]) -> AgentSkillRecord:
    _exact(document, _RECORD_FIELDS, "agent skill checkpoint record")
    recipe_value = document["recipe"]
    if isinstance(recipe_value, (str, bytes, bytearray)) or not isinstance(recipe_value, Sequence):
        raise ValueError("recipe must be a sequence")
    recipe: list[tuple[str, Mapping[str, JsonValue]]] = []
    for item in recipe_value:
        if not isinstance(item, Mapping):
            raise ValueError("recipe entry must be a mapping")
        _exact(item, _RECIPE_FIELDS, "agent skill recipe entry")
        recipe.append((_string(item["action_type"], "action_type"), _payload(item["payload"])))
    return AgentSkillRecord(
        skill_id=_string(document["skill_id"], "skill_id"),
        version=_string(document["version"], "version"),
        summary=_string(document["summary"], "summary"),
        tags=_strings(document["tags"], "tags"),
        source_refs=_strings(document["source_refs"], "source_refs"),
        recipe=tuple(recipe),
        success_count=_integer(document["success_count"], "success_count"),
        failure_count=_integer(document["failure_count"], "failure_count"),
    )


@dataclass(frozen=True, slots=True)
class AgentSkillLibraryCheckpoint:
    records: tuple[AgentSkillRecord, ...]
    schema_version: str = AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent skill library checkpoint schema")
        if not isinstance(self.records, tuple) or any(not isinstance(record, AgentSkillRecord) for record in self.records):
            raise ValueError("records must be a tuple of AgentSkillRecord")
        skill_ids = tuple(record.skill_id for record in self.records)
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("agent skill library checkpoint contains duplicate skill ids")
        for record in self.records:
            _record_to_dict(record)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "records": [_record_to_dict(record) for record in self.records],
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentSkillLibraryCheckpoint":
        _exact(document, _CHECKPOINT_FIELDS, "agent skill library checkpoint")
        if document["schema_version"] != AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent skill library checkpoint schema")
        rows = document["records"]
        if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
            raise ValueError("records must be a sequence")
        records: list[AgentSkillRecord] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("agent skill checkpoint record must be a mapping")
            records.append(_record_from_dict(row))
        return cls(records=tuple(records))


__all__ = [
    "AGENT_SKILL_LIBRARY_CHECKPOINT_SCHEMA",
    "AgentSkillLibraryCheckpoint",
]
