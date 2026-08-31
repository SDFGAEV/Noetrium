from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import strict_finite_json_digest as canonical_digest


@dataclass(frozen=True, slots=True)
class ArtifactLineageEdge:
    parent_artifact_id: str
    child_artifact_id: str
    relation_type: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.parent_artifact_id, self.child_artifact_id, self.relation_type)):
            raise ValueError("artifact lineage identity fields must be non-empty")
        if self.parent_artifact_id == self.child_artifact_id:
            raise ValueError("artifact lineage cannot contain a self-edge")
        if any(not ref.strip() for ref in self.evidence_refs) or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("artifact lineage evidence refs must be non-empty and unique")

    @property
    def edge_id(self) -> str:
        return canonical_digest(
            {
                "parent_artifact_id": self.parent_artifact_id,
                "child_artifact_id": self.child_artifact_id,
                "relation_type": self.relation_type,
                "evidence_refs": self.evidence_refs,
            }
        )


class ArtifactLineageCycle(RuntimeError):
    pass


class ArtifactLineageConflict(RuntimeError):
    pass


class ArtifactLineageCorruptionError(RuntimeError):
    pass


__all__ = [
    "ArtifactLineageConflict",
    "ArtifactLineageCorruptionError",
    "ArtifactLineageCycle",
    "ArtifactLineageEdge",
]
