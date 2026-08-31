"""Shared Experimentation identity facets; no durable authority lives here."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest

_HEX = frozenset("0123456789abcdef")


def _sha(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return value


class ReplayLevel(StrEnum):
    EXACT = "exact"
    CHECKPOINT = "checkpoint"
    OBSERVATIONAL = "observational"


@dataclass(frozen=True, slots=True)
class OptionalIdentityFacet:
    """Explicitly applicable or absent identity; never a placeholder digest."""

    digest: str | None = None

    def __post_init__(self) -> None:
        if self.digest is not None:
            _sha(self.digest, "optional identity facet digest")

    @property
    def applicable(self) -> bool:
        return self.digest is not None

    def facet_digest(self) -> str:
        return canonical_digest({"applicable": self.applicable, "digest": self.digest})


@dataclass(frozen=True, slots=True)
class RunResearchSemanticsReference:
    research_plan_digest: str
    study_plan_digest: str
    measurement_protocol_digest: str
    trial_protocol_digest: str
    intervention: OptionalIdentityFacet
    topology: OptionalIdentityFacet
    participant_schedule: OptionalIdentityFacet
    revision: OptionalIdentityFacet
    replay_level: ReplayLevel

    def __post_init__(self) -> None:
        for field, value in (("research_plan_digest", self.research_plan_digest), ("study_plan_digest", self.study_plan_digest), ("measurement_protocol_digest", self.measurement_protocol_digest), ("trial_protocol_digest", self.trial_protocol_digest)):
            _sha(value, f"run research semantics {field}")
        for field, value in (("intervention", self.intervention), ("topology", self.topology), ("participant_schedule", self.participant_schedule), ("revision", self.revision)):
            if type(value) is not OptionalIdentityFacet:
                raise TypeError(f"run research semantics {field} must be OptionalIdentityFacet")
        if not isinstance(self.replay_level, ReplayLevel):
            raise TypeError("run research semantics replay_level must be ReplayLevel")

    @property
    def checkpoint_compatibility_digest(self) -> str:
        return canonical_digest({
            "trial_protocol_digest": self.trial_protocol_digest,
            "intervention": self.intervention,
            "topology": self.topology,
            "participant_schedule": self.participant_schedule,
            "revision": self.revision,
            "replay_level": self.replay_level.value,
        })

    def digest(self) -> str:
        return canonical_digest(self)


__all__ = ["OptionalIdentityFacet", "ReplayLevel", "RunResearchSemanticsReference"]
