from __future__ import annotations

import sqlite3

import pytest

from research_platform.artifact.catalog.api import ArtifactKind, ArtifactRecord
from research_platform.data.dataset.api import DatasetIdentity, DatasetVersion
from research_platform.data.fact.api import DurableFact, FactCriticality
from research_platform.observability.telemetry.metric.providers.sqlite_reader import TelemetryReadSession
from research_platform.observability.telemetry.metric.providers.sqlite_schema import initialize_telemetry_schema
from research_platform.scope.api import ScopeIdentity, ScopeKind


def _scope() -> ScopeIdentity:
    return ScopeIdentity(ScopeKind.RUN, "algorithm-run")


def test_artifact_record_validates_tail_lineage_and_metadata_entries() -> None:
    with pytest.raises(ValueError, match="lineage references"):
        ArtifactRecord(
            "artifact", ArtifactKind.SCIENTIFIC, _scope(), "a" * 64, "artifact://result",
            "project.method", lineage=("valid:one", "valid:two", ""),
        )
    with pytest.raises(ValueError, match="metadata keys"):
        ArtifactRecord(
            "artifact", ArtifactKind.SCIENTIFIC, _scope(), "a" * 64, "artifact://result",
            "project.method", metadata=(("one", "1"), ("two", "2"), ("", "3")),
        )


def test_dataset_version_validates_tail_parent_tag_and_metadata_entries() -> None:
    with pytest.raises(ValueError, match="parent_versions"):
        DatasetVersion(
            DatasetIdentity("dataset", "v1"), _scope(), "b" * 64, "artifact://dataset",
            parent_versions=("source@v1", "source@v2", ""),
        )
    with pytest.raises(ValueError, match="tags"):
        DatasetVersion(
            DatasetIdentity("dataset", "v1"), _scope(), "b" * 64, "artifact://dataset",
            tags=("one", "two", ""),
        )
    with pytest.raises(ValueError, match="metadata keys"):
        DatasetVersion(
            DatasetIdentity("dataset", "v1"), _scope(), "b" * 64, "artifact://dataset",
            metadata=(("one", "1"), ("two", "2"), ("", "3")),
        )


def test_durable_fact_validates_tail_artifact_and_state_references() -> None:
    with pytest.raises(ValueError, match="artifact_refs"):
        DurableFact(
            "fact", "project.fact", "v1", FactCriticality.REQUIRED, {},
            artifact_refs=("artifact:one", "artifact:two", ""),
        )
    with pytest.raises(ValueError, match="state_refs"):
        DurableFact(
            "fact", "project.fact", "v1", FactCriticality.REQUIRED, {},
            state_refs=("state:one", "state:two", ""),
        )


def test_telemetry_read_session_materializes_every_requested_typed_row(tmp_path) -> None:
    path = tmp_path / "metrics.sqlite3"
    db = sqlite3.connect(path)
    try:
        initialize_telemetry_schema(db)
        with db:
            for index in range(5):
                db.execute(
                    "INSERT INTO metric_observations("
                    "metric,value,timestamp,run_id,trace_id,span_id,participant_generations_json,dimensions_json"
                    ") VALUES(?,?,?,?,?,?,?,?)",
                    ("latency", float(index + 1), float(index), "run", "trace", "span", "{}", "{}"),
                )
    finally:
        db.close()

    session = TelemetryReadSession(lambda: sqlite3.connect(path))
    try:
        rows = session.query(run_id="run", metric="latency", decision_cycle_id=None, limit=5)
        assert len(rows) == 5
        assert tuple(row[0] for row in rows) == (1, 2, 3, 4, 5)
    finally:
        session.close()
