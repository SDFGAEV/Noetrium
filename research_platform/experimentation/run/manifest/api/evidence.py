from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest


_HEX = frozenset("0123456789abcdef")
EVIDENCE_BUNDLE_SCHEMA_VERSION = "1"


def _require_identity(value: object, field: str) -> str:
    text = _require_non_empty_string(value, field)
    if "/" in text or "\\" in text or text in {".", ".."}:
        raise ValueError(f"evidence bundle {field} is invalid")
    return text


def _require_non_empty_string(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"evidence bundle {field} must be a non-empty string")
    return value


def _require_sha256(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(character not in _HEX for character in value.lower()):
        raise ValueError(f"evidence bundle {field} must be SHA-256")
    return value


def _require_non_negative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"evidence bundle {field} must be a non-negative integer")
    return value


def _require_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"evidence bundle {field} must be boolean")
    return value


class EvidenceBundleStatus(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, order=True)
class EvidenceStreamDescriptor:
    stream_id: str
    family: str
    schema_version: str
    artifact_ref: str
    record_count: int
    content_sha256: str
    required: bool
    source_of_truth: bool

    def __post_init__(self) -> None:
        _require_identity(self.stream_id, "stream_id")
        _require_non_empty_string(self.family, "stream family")
        _require_non_empty_string(self.schema_version, "stream schema_version")
        _require_non_empty_string(self.artifact_ref, "stream artifact_ref")
        _require_non_negative_int(self.record_count, "stream record_count")
        _require_sha256(self.content_sha256, "stream content_sha256")
        _require_bool(self.required, "stream required")
        _require_bool(self.source_of_truth, "stream source_of_truth")


def _validate_source_stream_ids(values: tuple[str, ...]) -> None:
    if type(values) is not tuple or not values:
        raise ValueError("derived evidence artifact requires source streams")
    normalized = tuple(_require_identity(value, "derived source stream_id") for value in values)
    if tuple(sorted(set(normalized))) != normalized:
        raise ValueError("derived evidence source stream ids must be unique and ordered")


@dataclass(frozen=True, slots=True, order=True)
class DerivedEvidenceArtifact:
    artifact_id: str
    artifact_kind: str
    artifact_ref: str
    content_sha256: str
    derived_from_stream_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identity(self.artifact_id, "artifact_id")
        _require_non_empty_string(self.artifact_kind, "artifact_kind")
        _require_non_empty_string(self.artifact_ref, "artifact_ref")
        _require_sha256(self.content_sha256, "artifact content_sha256")
        _validate_source_stream_ids(self.derived_from_stream_ids)


def _require_unique_ordered_ids(values: tuple[str, ...], field: str) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"{field} must be unique and ordered")


def _validate_stream_collection(streams: tuple[EvidenceStreamDescriptor, ...]) -> tuple[str, ...]:
    if type(streams) is not tuple or not streams:
        raise ValueError("evidence bundle requires at least one stream")
    if any(type(stream) is not EvidenceStreamDescriptor for stream in streams):
        raise ValueError("evidence bundle streams must be typed descriptors")
    stream_ids = tuple(stream.stream_id for stream in streams)
    _require_unique_ordered_ids(stream_ids, "evidence streams")
    if not any(stream.required and stream.source_of_truth for stream in streams):
        raise ValueError("evidence bundle requires an authoritative required stream")
    return stream_ids


def _validate_complete_streams(status: EvidenceBundleStatus, streams: tuple[EvidenceStreamDescriptor, ...]) -> None:
    if status is EvidenceBundleStatus.COMPLETE and any(
        stream.required and stream.record_count == 0 for stream in streams
    ):
        raise ValueError("complete evidence bundle cannot have an empty required stream")


def _validate_artifacts(
    artifacts: tuple[DerivedEvidenceArtifact, ...],
    stream_ids: tuple[str, ...],
) -> None:
    if type(artifacts) is not tuple or any(
        type(artifact) is not DerivedEvidenceArtifact for artifact in artifacts
    ):
        raise ValueError("derived evidence artifacts must be typed descriptors")
    artifact_ids = tuple(artifact.artifact_id for artifact in artifacts)
    _require_unique_ordered_ids(artifact_ids, "derived evidence artifacts")
    available = set(stream_ids)
    for artifact in artifacts:
        missing = set(artifact.derived_from_stream_ids) - available
        if missing:
            raise ValueError(f"derived evidence artifact references missing streams: {sorted(missing)}")


@dataclass(frozen=True, slots=True)
class EvidenceBundleManifest:
    """Immutable index over raw scientific streams and rebuildable projections."""

    schema_version: str
    bundle_id: str
    run_id: str
    run_manifest_digest: str
    status: EvidenceBundleStatus
    source_checkpoint_id: str | None
    streams: tuple[EvidenceStreamDescriptor, ...]
    derived_artifacts: tuple[DerivedEvidenceArtifact, ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != EVIDENCE_BUNDLE_SCHEMA_VERSION:
            raise ValueError("evidence bundle schema_version is unsupported")
        _require_identity(self.bundle_id, "bundle_id")
        _require_identity(self.run_id, "run_id")
        _require_sha256(self.run_manifest_digest, "run_manifest_digest")
        if type(self.status) is not EvidenceBundleStatus:
            raise ValueError("evidence bundle status must be EvidenceBundleStatus")
        if self.source_checkpoint_id is not None:
            _require_non_empty_string(self.source_checkpoint_id, "source_checkpoint_id")
        stream_ids = _validate_stream_collection(self.streams)
        _validate_complete_streams(self.status, self.streams)
        _validate_artifacts(self.derived_artifacts, stream_ids)

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class EvidenceBundleReceipt:
    bundle_id: str
    run_id: str
    run_manifest_digest: str
    manifest_ref: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        _require_identity(self.bundle_id, "receipt bundle_id")
        _require_identity(self.run_id, "receipt run_id")
        _require_sha256(self.run_manifest_digest, "receipt run_manifest_digest")
        _require_non_empty_string(self.manifest_ref, "receipt manifest_ref")
        _require_sha256(self.manifest_sha256, "receipt manifest_sha256")


__all__ = [
    "DerivedEvidenceArtifact",
    "EVIDENCE_BUNDLE_SCHEMA_VERSION",
    "EvidenceBundleManifest",
    "EvidenceBundleReceipt",
    "EvidenceBundleStatus",
    "EvidenceStreamDescriptor",
]
