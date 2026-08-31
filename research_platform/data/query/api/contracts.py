from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.scope.api import ScopeIdentity


class ResearchDimensionKind(StrEnum):
    PROJECT = "project"
    STUDY = "study"
    VARIANT = "variant"
    ASSIGNMENT = "assignment"
    RUN = "run"
    METHOD = "method"
    COMPONENT = "component"
    MODEL = "model"
    ENVIRONMENT = "environment"
    BENCHMARK = "benchmark"
    TASK = "task"
    SPLIT = "split"
    MEASUREMENT = "measurement"
    ANALYSIS = "analysis"
    DATASET = "dataset"
    REPORT = "report"
    PUBLICATION = "publication"


class ResearchResultKind(StrEnum):
    ARTIFACT = "artifact"
    DATASET = "dataset"
    EVIDENCE = "evidence"
    MEASUREMENT = "measurement"
    ANALYSIS = "analysis"
    REPORT = "report"
    PUBLICATION = "publication"


class ResearchSourceDisposition(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    INCOMPLETE = "incomplete"
    STALE = "stale"


class ResearchQueryGapKind(StrEnum):
    RESULT_KIND = "result_kind"
    DIMENSION = "dimension"
    PINNED_SOURCE = "pinned_source"


@dataclass(frozen=True, slots=True, order=True)
class ResearchDimension:
    kind: ResearchDimensionKind
    value: str
    revision: str | None = None

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("research dimension value must be non-empty")
        if self.revision is not None and not self.revision.strip():
            raise ValueError("research dimension revision must be non-empty when present")

@dataclass(frozen=True, slots=True, order=True)
class ResearchResultReference:
    kind: ResearchResultKind
    result_id: str
    source_authority: str

    def __post_init__(self) -> None:
        if not self.result_id.strip() or not self.source_authority.strip():
            raise ValueError("research result reference identity fields must be non-empty")


@dataclass(frozen=True, slots=True)
class ResearchResultRecord:
    reference: ResearchResultReference
    scope: ScopeIdentity
    content_sha256: str | None = None
    schema_ref: str | None = None
    dimensions: tuple[ResearchDimension, ...] = ()
    lineage: tuple[ResearchResultReference, ...] = ()

    def __post_init__(self) -> None:
        if self.content_sha256 is not None and (
            len(self.content_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.content_sha256)
        ):
            raise ValueError("research result content_sha256 must be lowercase SHA-256")
        if self.schema_ref is not None and not self.schema_ref.strip():
            raise ValueError("research result schema_ref must be non-empty when present")
        dimension_kinds = [row.kind for row in self.dimensions]
        if len(set(dimension_kinds)) != len(dimension_kinds):
            raise ValueError("research result dimensions must have unique kinds")
        if len(set(self.lineage)) != len(self.lineage):
            raise ValueError("research result lineage references must be unique")


@dataclass(frozen=True, slots=True, order=True)
class ResearchSourceCut:
    source_id: str
    query_digest: str
    cut_digest: str
    record_count: int

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("research source cut source_id must be non-empty")
        for name, value in (("query_digest", self.query_digest), ("cut_digest", self.cut_digest)):
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"research source cut {name} must be lowercase SHA-256")
        if isinstance(self.record_count, bool) or not isinstance(self.record_count, int) or self.record_count < 0:
            raise ValueError("research source cut record_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ResearchResultQuery:
    dimensions: tuple[ResearchDimension, ...] = ()
    kinds: tuple[ResearchResultKind, ...] = ()
    pinned_source_cuts: tuple[ResearchSourceCut, ...] = ()
    limit: int = 1000

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or not 1 <= self.limit <= 10_000:
            raise ValueError("research result query limit must be an integer in [1, 10000]")
        dimension_kinds = [row.kind for row in self.dimensions]
        if len(set(dimension_kinds)) != len(dimension_kinds):
            raise ValueError("research result query dimensions must have unique kinds")
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError("research result query kinds must be unique")
        source_ids = [row.source_id for row in self.pinned_source_cuts]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("research result query pinned source cuts must have unique source ids")


@dataclass(frozen=True, slots=True)
class ResearchSourceSnapshot:
    source_id: str
    cut: ResearchSourceCut
    records: tuple[ResearchResultRecord, ...]

    def __post_init__(self) -> None:
        if self.source_id != self.cut.source_id:
            raise ValueError("research source snapshot identity does not match its cut")
        if len(self.records) != self.cut.record_count:
            raise ValueError("research source snapshot record count does not match its cut")
        if any(row.reference.source_authority != self.source_id for row in self.records):
            raise ValueError("research source snapshot contains a foreign source-authority record")

@dataclass(frozen=True, slots=True)
class ResearchSourceStatus:
    source_id: str
    disposition: ResearchSourceDisposition
    cut: ResearchSourceCut | None = None
    diagnostic_code: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("research source status source_id must be non-empty")
        if self.disposition is ResearchSourceDisposition.COMPLETE and self.cut is None:
            raise ValueError("complete research source status requires a source cut")
        if self.disposition is not ResearchSourceDisposition.COMPLETE and not self.diagnostic_code:
            raise ValueError("non-complete research source status requires a diagnostic code")


@dataclass(frozen=True, slots=True, order=True)
class ResearchQueryGap:
    kind: ResearchQueryGapKind
    value: str
    diagnostic_code: str

    def __post_init__(self) -> None:
        if not self.value.strip() or not self.diagnostic_code.strip():
            raise ValueError("research query gap value/diagnostic_code must be non-empty")


@dataclass(frozen=True, slots=True)
class ResearchResultPage:
    query_digest: str
    input_cut_digest: str
    records: tuple[ResearchResultRecord, ...]
    sources: tuple[ResearchSourceStatus, ...]
    matched_count: int
    truncated: bool
    gaps: tuple[ResearchQueryGap, ...] = ()
    complete: bool = False

    def __post_init__(self) -> None:
        for name, value in (("query_digest", self.query_digest), ("input_cut_digest", self.input_cut_digest)):
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"research result page {name} must be lowercase SHA-256")
        if isinstance(self.matched_count, bool) or not isinstance(self.matched_count, int) or self.matched_count < 0:
            raise ValueError("research result page matched_count must be a non-negative integer")
        if not isinstance(self.truncated, bool) or not isinstance(self.complete, bool):
            raise TypeError("research result page truncated/complete must be bool")
        if self.matched_count < len(self.records):
            raise ValueError("research result page matched_count cannot be smaller than returned records")
        if self.truncated != (self.matched_count > len(self.records)):
            raise ValueError("research result page truncation disagrees with matched/returned counts")
        expected_complete = not self.gaps and not self.truncated and all(
            row.disposition is ResearchSourceDisposition.COMPLETE for row in self.sources
        )
        if self.complete != expected_complete:
            raise ValueError("research result page completeness disagrees with sources/gaps/truncation")


class ResearchQuerySourceError(RuntimeError):
    def __init__(
        self,
        source_id: str,
        code: str,
        message: str,
        *,
        disposition: ResearchSourceDisposition = ResearchSourceDisposition.UNAVAILABLE,
    ) -> None:
        if not source_id.strip() or not code.strip():
            raise ValueError("research query source error identity/code must be non-empty")
        if disposition not in (ResearchSourceDisposition.UNAVAILABLE, ResearchSourceDisposition.INCOMPLETE):
            raise ValueError("research query source error disposition must be unavailable or incomplete")
        self.source_id = source_id
        self.code = code
        self.disposition = disposition
        super().__init__(f"research query source failed [{source_id}:{code}]: {message}")


__all__ = [
    "ResearchDimension",
    "ResearchDimensionKind",
    "ResearchQueryGap",
    "ResearchQueryGapKind",
    "ResearchQuerySourceError",
    "ResearchResultKind",
    "ResearchResultPage",
    "ResearchResultQuery",
    "ResearchResultRecord",
    "ResearchResultReference",
    "ResearchSourceCut",
    "ResearchSourceDisposition",
    "ResearchSourceSnapshot",
    "ResearchSourceStatus",
]
