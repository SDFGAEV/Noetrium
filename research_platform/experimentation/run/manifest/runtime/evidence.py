from __future__ import annotations

import json
import hashlib
from pathlib import Path

from research_platform.experimentation.run.api import RunArtifactKind, RunArtifactStorePort
from research_platform.platform.kernel import canonical_bytes

from ..api import (
    DerivedEvidenceArtifact,
    EvidenceBundleManifest,
    EvidenceBundleReceipt,
    EvidenceBundleStatus,
    EvidenceStreamDescriptor,
)


class EvidenceBundleDecodeError(ValueError):
    pass


def encode_evidence_bundle_manifest(manifest: EvidenceBundleManifest) -> bytes:
    return canonical_bytes(manifest, indent=2) + b"\n"


_BUNDLE_FIELDS = frozenset({
    "schema_version", "bundle_id", "run_id", "run_manifest_digest", "status",
    "source_checkpoint_id", "streams", "derived_artifacts",
})
_STREAM_FIELDS = frozenset({
    "stream_id", "family", "schema_version", "artifact_ref",
    "record_count", "content_sha256", "required", "source_of_truth",
})
_ARTIFACT_FIELDS = frozenset({
    "artifact_id", "artifact_kind", "artifact_ref", "content_sha256",
    "derived_from_stream_ids",
})


def _require_document(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError("evidence bundle payload must be bytes")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != _BUNDLE_FIELDS:
        raise TypeError("evidence bundle fields are not exact")
    return document


def _require_string(row: dict[str, object], field: str, scope: str) -> str:
    value = row[field]
    if type(value) is not str:
        raise TypeError(f"{scope} {field} must be a string")
    return value


def _decode_stream(row: object) -> EvidenceStreamDescriptor:
    if not isinstance(row, dict) or set(row) != _STREAM_FIELDS:
        raise TypeError("evidence stream fields are not exact")
    strings = {field: _require_string(row, field, "evidence stream") for field in (
        "stream_id", "family", "schema_version", "artifact_ref", "content_sha256"
    )}
    if type(row["record_count"]) is not int:
        raise TypeError("evidence stream record_count must be an integer")
    if type(row["required"]) is not bool or type(row["source_of_truth"]) is not bool:
        raise TypeError("evidence stream flags must be booleans")
    return EvidenceStreamDescriptor(
        strings["stream_id"], strings["family"], strings["schema_version"],
        strings["artifact_ref"], row["record_count"], strings["content_sha256"],
        row["required"], row["source_of_truth"],
    )


def _decode_streams(value: object) -> tuple[EvidenceStreamDescriptor, ...]:
    if not isinstance(value, list):
        raise TypeError("evidence bundle streams must be a list")
    return tuple(_decode_stream(row) for row in value)


def _decode_artifact(row: object) -> DerivedEvidenceArtifact:
    if not isinstance(row, dict) or set(row) != _ARTIFACT_FIELDS:
        raise TypeError("derived evidence artifact fields are not exact")
    values = {field: _require_string(row, field, "derived evidence artifact") for field in (
        "artifact_id", "artifact_kind", "artifact_ref", "content_sha256"
    )}
    source_ids = row["derived_from_stream_ids"]
    if not isinstance(source_ids, list) or any(type(item) is not str for item in source_ids):
        raise TypeError("derived evidence source ids must be strings")
    return DerivedEvidenceArtifact(
        values["artifact_id"], values["artifact_kind"], values["artifact_ref"],
        values["content_sha256"], tuple(source_ids),
    )


def _decode_artifacts(value: object) -> tuple[DerivedEvidenceArtifact, ...]:
    if not isinstance(value, list):
        raise TypeError("evidence bundle derived_artifacts must be a list")
    return tuple(_decode_artifact(row) for row in value)


def _decode_checkpoint(value: object) -> str | None:
    if value is not None and type(value) is not str:
        raise TypeError("evidence bundle source_checkpoint_id must be a string or null")
    return value


def _build_evidence_bundle(document: dict[str, object]) -> EvidenceBundleManifest:
    return EvidenceBundleManifest(
        schema_version=_require_string(document, "schema_version", "evidence bundle"),
        bundle_id=_require_string(document, "bundle_id", "evidence bundle"),
        run_id=_require_string(document, "run_id", "evidence bundle"),
        run_manifest_digest=_require_string(document, "run_manifest_digest", "evidence bundle"),
        status=EvidenceBundleStatus(_require_string(document, "status", "evidence bundle")),
        source_checkpoint_id=_decode_checkpoint(document["source_checkpoint_id"]),
        streams=_decode_streams(document["streams"]),
        derived_artifacts=_decode_artifacts(document["derived_artifacts"]),
    )


def decode_evidence_bundle_manifest(raw: bytes) -> EvidenceBundleManifest:
    try:
        return _build_evidence_bundle(_require_document(raw))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise EvidenceBundleDecodeError(
            "evidence bundle violates the frozen manifest contract"
        ) from exc


def load_evidence_bundle_manifest(path: str | Path) -> EvidenceBundleManifest:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise EvidenceBundleDecodeError(f"evidence bundle manifest is not a regular file: {target}")
    try:
        return decode_evidence_bundle_manifest(target.read_bytes())
    except OSError as exc:
        raise EvidenceBundleDecodeError("evidence bundle manifest cannot be read") from exc


class RunArtifactEvidenceBundlePublisher:
    """Publish one validated final manifest through the run artifact authority."""

    def __init__(self, artifacts: RunArtifactStorePort) -> None:
        self._artifacts = artifacts

    def publish(self, manifest: EvidenceBundleManifest) -> EvidenceBundleReceipt:
        encoded = canonical_bytes(manifest)
        manifest_ref = self._artifacts.publish_text(
            f"evidence/{manifest.bundle_id}/manifest.json",
            encoded.decode("utf-8"),
            kind=RunArtifactKind.EVIDENCE,
        )
        return EvidenceBundleReceipt(
            manifest.bundle_id,
            manifest.run_id,
            manifest.run_manifest_digest,
            manifest_ref,
            hashlib.sha256(encoded).hexdigest(),
        )


__all__ = [
    "EvidenceBundleDecodeError",
    "RunArtifactEvidenceBundlePublisher",
    "decode_evidence_bundle_manifest",
    "encode_evidence_bundle_manifest",
    "load_evidence_bundle_manifest",
]
