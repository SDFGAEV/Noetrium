from __future__ import annotations
from tests._concurrency_support import run_artifact_store

import json
import hashlib
from dataclasses import asdict
from pathlib import Path

import pytest

from research_platform.experimentation.run.manifest.api import (
    DerivedEvidenceArtifact,
    EvidenceBundleManifest,
    EvidenceBundleReceipt,
    EvidenceBundleStatus,
    EvidenceStreamDescriptor,
)
from research_platform.experimentation.run.manifest.runtime import (
    RunArtifactEvidenceBundlePublisher,
    decode_evidence_bundle_manifest,
    encode_evidence_bundle_manifest,
)
from research_platform.experimentation.run.runtime import DirectoryRunArtifactStore


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _manifest() -> EvidenceBundleManifest:
    return EvidenceBundleManifest(
        schema_version="1",
        bundle_id="episode-1",
        run_id="run-1",
        run_manifest_digest=SHA_C,
        status=EvidenceBundleStatus.COMPLETE,
        source_checkpoint_id="checkpoint-1",
        streams=(
            EvidenceStreamDescriptor(
                "environment-events",
                "environment.raw",
                "1",
                "raw/environment.jsonl",
                4,
                SHA_A,
                True,
                True,
            ),
            EvidenceStreamDescriptor(
                "study-events",
                "study.raw",
                "1",
                "raw/study.jsonl",
                2,
                SHA_B,
                True,
                True,
            ),
        ),
        derived_artifacts=(
            DerivedEvidenceArtifact(
                "replay-overview",
                "replay_projection",
                "projections/replay.json",
                SHA_B,
                ("environment-events", "study-events"),
            ),
        ),
    )


def test_evidence_bundle_publishes_one_atomic_run_artifact(tmp_path: Path) -> None:
    manifest = _manifest()
    receipt = RunArtifactEvidenceBundlePublisher(run_artifact_store(tmp_path)).publish(
        manifest
    )

    target = tmp_path / "evidence" / "episode-1" / "manifest.json"
    assert receipt.run_manifest_digest == SHA_C
    assert receipt.manifest_ref == str(target)
    assert receipt.manifest_sha256 == manifest.digest
    assert receipt.manifest_sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["status"] == "complete"
    assert [row["stream_id"] for row in document["streams"]] == [
        "environment-events",
        "study-events",
    ]


def test_evidence_bundle_codec_round_trips_exact_contract() -> None:
    manifest = _manifest()

    assert decode_evidence_bundle_manifest(encode_evidence_bundle_manifest(manifest)) == manifest


def test_evidence_bundle_rejects_unsupported_schema_and_invalid_run_manifest_digest() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        EvidenceBundleManifest(**{**asdict(_manifest()), "schema_version": "2"})
    with pytest.raises(ValueError, match="run_manifest_digest"):
        EvidenceBundleManifest(**{**asdict(_manifest()), "run_manifest_digest": "not-a-sha"})


def test_evidence_bundle_decoder_rejects_unknown_fields() -> None:
    document = asdict(_manifest())
    document["undeclared"] = True

    with pytest.raises(ValueError, match="frozen manifest contract"):
        decode_evidence_bundle_manifest(json.dumps(document).encode())


def test_complete_evidence_bundle_rejects_empty_required_stream() -> None:
    stream = EvidenceStreamDescriptor(
        "environment-events", "environment.raw", "1", "raw/environment.jsonl", 0, SHA_A, True, True
    )
    with pytest.raises(ValueError, match="empty required stream"):
        EvidenceBundleManifest(
            "1", "episode-1", "run-1", SHA_C, EvidenceBundleStatus.COMPLETE, None, (stream,)
        )


def test_derived_evidence_cannot_reference_an_absent_raw_stream() -> None:
    stream = EvidenceStreamDescriptor(
        "environment-events", "environment.raw", "1", "raw/environment.jsonl", 1, SHA_A, True, True
    )
    artifact = DerivedEvidenceArtifact(
        "replay-overview", "projection", "projection.json", SHA_B, ("missing-stream",)
    )
    with pytest.raises(ValueError, match="missing streams"):
        EvidenceBundleManifest(
            "1", "episode-1", "run-1", SHA_C, EvidenceBundleStatus.COMPLETE, None, (stream,), (artifact,)
        )


def test_evidence_stream_rejects_bool_as_record_count_and_non_bool_flags() -> None:
    with pytest.raises(ValueError):
        EvidenceStreamDescriptor(
            "environment-events", "environment.raw", "1", "raw/environment.jsonl",
            True, SHA_A, True, True,
        )
    with pytest.raises(ValueError):
        EvidenceStreamDescriptor(
            "environment-events", "environment.raw", "1", "raw/environment.jsonl",
            1, SHA_A, 1, True,
        )


def test_evidence_bundle_requires_typed_status() -> None:
    stream = EvidenceStreamDescriptor(
        "environment-events", "environment.raw", "1", "raw/environment.jsonl",
        1, SHA_A, True, True,
    )
    with pytest.raises(ValueError, match="EvidenceBundleStatus"):
        EvidenceBundleManifest("1", "episode-1", "run-1", SHA_C, "complete", None, (stream,))


def test_evidence_bundle_receipt_rejects_malformed_publication_identity() -> None:
    valid = dict(
        bundle_id="episode-1", run_id="run-1", run_manifest_digest=SHA_C,
        manifest_ref="evidence/episode-1/manifest.json", manifest_sha256=SHA_A,
    )
    assert EvidenceBundleReceipt(**valid).manifest_sha256 == SHA_A
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "bundle_id": "../escape"})
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "run_id": " "})
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "run_manifest_digest": "not-a-sha"})
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "manifest_ref": ""})
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "manifest_sha256": "not-a-sha"})
    with pytest.raises(ValueError):
        EvidenceBundleReceipt(**{**valid, "manifest_sha256": True})
