from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


AGENT_MEMORY_CHECKPOINT_SCHEMA = "agent-memory.v2"
_RECORD_FIELDS = frozenset(
    {
        "memory_id",
        "plane",
        "kind",
        "content",
        "generation",
        "state_digest",
        "tags",
        "verified",
        "step",
        "artifact_refs",
    }
)
_CHECKPOINT_FIELDS = frozenset({"schema_version", "sequence_counter", "records"})


def _require_exact_fields(document: Mapping[str, Any], expected: frozenset[str], *, label: str) -> None:
    actual = frozenset(document)
    if actual != expected:
        raise ValueError(f"{label} fields mismatch: expected={sorted(expected)!r} actual={sorted(actual)!r}")


def _require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_integer(value: Any, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def _require_strings(value: Any, *, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a sequence of strings")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise ValueError(f"{field} must contain only strings")
    return result


@dataclass(frozen=True, slots=True)
class AgentMemoryCheckpointRecord:
    memory_id: str
    plane: str
    kind: str
    content: str
    generation: str
    state_digest: str
    tags: tuple[str, ...]
    verified: bool
    step: int
    artifact_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("memory_id", "plane", "kind", "content", "generation", "state_digest"):
            _require_string(getattr(self, field_name), field=field_name)
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        _require_integer(self.step, field="step")
        _require_strings(self.tags, field="tags")
        _require_strings(self.artifact_refs, field="artifact_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "plane": self.plane,
            "kind": self.kind,
            "content": self.content,
            "generation": self.generation,
            "state_digest": self.state_digest,
            "tags": list(self.tags),
            "verified": self.verified,
            "step": self.step,
            "artifact_refs": list(self.artifact_refs),
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentMemoryCheckpointRecord":
        _require_exact_fields(document, _RECORD_FIELDS, label="agent memory checkpoint record")
        verified = document["verified"]
        if not isinstance(verified, bool):
            raise ValueError("verified must be a boolean")
        return cls(
            memory_id=_require_string(document["memory_id"], field="memory_id"),
            plane=_require_string(document["plane"], field="plane"),
            kind=_require_string(document["kind"], field="kind"),
            content=_require_string(document["content"], field="content"),
            generation=_require_string(document["generation"], field="generation"),
            state_digest=_require_string(document["state_digest"], field="state_digest"),
            tags=_require_strings(document["tags"], field="tags"),
            verified=verified,
            step=_require_integer(document["step"], field="step"),
            artifact_refs=_require_strings(document["artifact_refs"], field="artifact_refs"),
        )


@dataclass(frozen=True, slots=True)
class AgentMemoryCheckpoint:
    sequence_counter: int
    records: tuple[AgentMemoryCheckpointRecord, ...]
    schema_version: str = AGENT_MEMORY_CHECKPOINT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != AGENT_MEMORY_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent memory checkpoint schema")
        _require_integer(self.sequence_counter, field="sequence_counter")
        if not isinstance(self.records, tuple) or any(
            not isinstance(record, AgentMemoryCheckpointRecord) for record in self.records
        ):
            raise ValueError("records must be a tuple of AgentMemoryCheckpointRecord")
        memory_ids = tuple(record.memory_id for record in self.records)
        if len(set(memory_ids)) != len(memory_ids):
            raise ValueError("agent memory checkpoint contains duplicate memory ids")
        if self.records and self.sequence_counter < max(record.step for record in self.records):
            raise ValueError("sequence_counter cannot precede persisted record steps")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sequence_counter": self.sequence_counter,
            "records": [record.to_dict() for record in self.records],
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AgentMemoryCheckpoint":
        _require_exact_fields(document, _CHECKPOINT_FIELDS, label="agent memory checkpoint")
        if document["schema_version"] != AGENT_MEMORY_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported agent memory checkpoint schema")
        rows = document["records"]
        if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
            raise ValueError("records must be a sequence")
        records: list[AgentMemoryCheckpointRecord] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("agent memory checkpoint record must be a mapping")
            records.append(AgentMemoryCheckpointRecord.from_dict(row))
        return cls(
            sequence_counter=_require_integer(document["sequence_counter"], field="sequence_counter"),
            records=tuple(records),
        )


__all__ = [
    "AGENT_MEMORY_CHECKPOINT_SCHEMA",
    "AgentMemoryCheckpoint",
    "AgentMemoryCheckpointRecord",
]
