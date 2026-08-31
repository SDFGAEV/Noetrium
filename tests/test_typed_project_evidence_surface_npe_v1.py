from __future__ import annotations

import pytest

from research_platform.artifact.catalog.api import (
    ArtifactKind,
    ArtifactRecord,
    ArtifactRetention,
)
from research_platform.data.dataset.api import DatasetIdentity, DatasetVersion
from research_platform.data.fact.api import DurableFact, FactCriticality, FactDecoderPort, FactSchema
from research_platform.data.fact.runtime import FactDecoderRegistry
from research_platform.data.record.api import ExecutionRecordPlane
from research_platform.observability.api import EventEnvelope
from research_platform.observability.status.api import HealthState, SubsystemSnapshot
from research_platform.platform.kernel import ExecutionContext, canonical_bytes, canonical_digest
from research_platform.scope.api import ScopeIdentity, ScopeKind


def _run_scope() -> ScopeIdentity:
    return ScopeIdentity(ScopeKind.RUN, "run-npe")


def test_public_artifact_record_carries_content_identity_and_run_lineage() -> None:
    digest = canonical_digest({"evidence": "result-v1"})
    record = ArtifactRecord(
        artifact_id="evidence/result.json",
        kind=ArtifactKind.SCIENTIFIC,
        scope=_run_scope(),
        digest=digest,
        location="artifact://run-npe/evidence/result.json",
        producer_component_id="project.method",
        producer_operation_id="operation-finalize",
        lineage=("artifact:input",),
        retention=ArtifactRetention.RUN,
        media_type="application/json",
    )

    assert record.scope.kind is ScopeKind.RUN
    assert record.scope.scope_id == "run-npe"
    assert record.digest == digest and len(record.digest) == 64
    assert record.producer_operation_id == "operation-finalize"
    assert record.lineage == ("artifact:input",)


def test_public_dataset_version_carries_content_digest_and_scope() -> None:
    digest = canonical_digest({"dataset": [1, 2, 3]})
    dataset = DatasetVersion(
        identity=DatasetIdentity("project-eval", "v1"),
        scope=_run_scope(),
        digest=digest,
        location="artifact://run-npe/datasets/project-eval.jsonl",
        schema_ref="schema:project-eval.v1",
        parent_versions=("project-source@v1",),
    )

    assert dataset.scope == _run_scope()
    assert dataset.digest == digest
    assert dataset.identity.key == "project-eval@v1"


def test_observability_event_is_explicitly_side_plane_not_authority() -> None:
    event = EventEnvelope(
        event_id="event-npe-1",
        event_type="project.environment.ready",
        context=ExecutionContext("run-npe", "trace-npe", "span-npe"),
        component_id="project.environment",
        payload={"ready": True},
        artifact_refs=("evidence/result.json",),
    )

    assert event.record_plane is ExecutionRecordPlane.SIDE_PLANE_OBSERVATION
    assert event.context.run_id == "run-npe"
    assert event.artifact_refs == ("evidence/result.json",)


def test_project_status_is_read_only_projection_with_evidence_refs() -> None:
    snapshot = SubsystemSnapshot(
        subsystem="environment.reference-counter",
        state=HealthState.READY,
        summary="reference environment ready",
        evidence=("artifact:evidence/result.json",),
        reason_codes=("environment.ready",),
        next_commands=("project inspect evidence",),
    )

    assert snapshot.state is HealthState.READY
    assert snapshot.evidence == ("artifact:evidence/result.json",)
    assert snapshot.reason_codes == ("environment.ready",)

def test_public_artifact_record_rejects_tail_lineage_and_metadata_corruption() -> None:
    with pytest.raises(ValueError, match="lineage references"):
        ArtifactRecord(
            artifact_id="evidence/result.json", kind=ArtifactKind.SCIENTIFIC, scope=_run_scope(),
            digest="a" * 64, location="artifact://run-npe/evidence/result.json",
            producer_component_id="project.method", lineage=("artifact:one", "artifact:two", ""),
        )
    with pytest.raises(ValueError, match="metadata keys"):
        ArtifactRecord(
            artifact_id="evidence/result.json", kind=ArtifactKind.SCIENTIFIC, scope=_run_scope(),
            digest="a" * 64, location="artifact://run-npe/evidence/result.json",
            producer_component_id="project.method", metadata=(("one", "1"), ("two", "2"), ("", "3")),
        )


def test_public_dataset_version_rejects_tail_parent_tag_and_metadata_corruption() -> None:
    with pytest.raises(ValueError, match="parent_versions"):
        DatasetVersion(
            DatasetIdentity("project-eval", "v1"), _run_scope(), "b" * 64,
            "artifact://run-npe/datasets/project-eval.jsonl", parent_versions=("source@v1", "source@v2", ""),
        )
    with pytest.raises(ValueError, match="tags"):
        DatasetVersion(
            DatasetIdentity("project-eval", "v1"), _run_scope(), "b" * 64,
            "artifact://run-npe/datasets/project-eval.jsonl", tags=("one", "two", ""),
        )
    with pytest.raises(ValueError, match="metadata keys"):
        DatasetVersion(
            DatasetIdentity("project-eval", "v1"), _run_scope(), "b" * 64,
            "artifact://run-npe/datasets/project-eval.jsonl", metadata=(("one", "1"), ("two", "2"), ("", "3")),
        )


def test_fact_decoder_is_schema_bound_and_typed() -> None:
    class IntFactDecoder:
        schema = FactSchema[int]("project.score", "v1")

        def decode(self, fact: DurableFact) -> int:
            value = fact.payload.get("value")
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("project.score value must be an integer")
            return value

    decoder = IntFactDecoder()
    assert isinstance(decoder, FactDecoderPort)
    registry = FactDecoderRegistry((decoder,))
    fact = DurableFact(
        "score-1", "project.score", "v1", FactCriticality.REQUIRED, {"value": 7}
    )
    schema = FactSchema[int]("project.score", "v1")
    assert registry.decoder_for(schema) is decoder
    assert registry.decode_as(fact, schema) == 7


def test_fact_decoder_rejects_schema_mismatch_before_decode() -> None:
    class IntFactDecoder:
        schema = FactSchema[int]("project.score", "v1")

        def decode(self, fact: DurableFact) -> int:
            raise AssertionError("mismatched fact must be rejected before decoder invocation")

    registry = FactDecoderRegistry((IntFactDecoder(),))
    fact = DurableFact(
        "score-2", "project.score", "v2", FactCriticality.REQUIRED, {"value": 9}
    )
    with pytest.raises(ValueError, match="does not match requested typed schema"):
        registry.decode_as(fact, FactSchema[int]("project.score", "v1"))


def test_role05_canonical_encoding_uses_kernel_exact_bytes() -> None:
    from research_platform.data._canonical import canonical_bytes as data_canonical_bytes
    payload = {"b": (2, 3), "a": {"nested": True}, "finite": 1.25}
    expected = b'{"a":{"nested":true},"b":[2,3],"finite":1.25}'
    assert canonical_bytes(payload) == expected
    assert data_canonical_bytes(payload) == expected


def test_data_strict_decoder_rejects_duplicate_keys_and_nonfinite_constants() -> None:
    from research_platform.data._canonical import DataCanonicalDecodingError, strict_json_loads
    with pytest.raises(DataCanonicalDecodingError, match="duplicate object key"):
        strict_json_loads('{"a":1,"a":2}')
    with pytest.raises(DataCanonicalDecodingError, match="non-finite constant"):
        strict_json_loads('{"value":NaN}')
