from __future__ import annotations

import hashlib

import pytest

from research_platform.artifact.catalog.api import ArtifactKind, ArtifactRecord
from research_platform.artifact.catalog.runtime import InMemoryArtifactRegistry
from research_platform.artifact.content.api import ArtifactStorageVerificationError
from research_platform.artifact.content.composition import (
    compose_filesystem_artifact_storage_bindings,
)
from research_platform.data.dataset.api import DatasetIdentity, DatasetVersion
from research_platform.data.dataset.runtime import InMemoryDatasetRegistry
from research_platform.data.query.api import ResearchResultKind, ResearchResultQuery
from research_platform.data.query.cross.composition import (
    compose_builtin_research_result_query,
)
from research_platform.scope.api import PLATFORM_SCOPE
from research_platform.scope.runtime import InMemoryScopeRegistry


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_common_artifact_storage_composition_verifies_filesystem_bytes(tmp_path) -> None:
    payload = b"portable-composition-content"
    content = tmp_path / "artifact.bin"
    content.write_bytes(payload)

    assembly = compose_filesystem_artifact_storage_bindings(tmp_path / "bindings.sqlite3")
    binding = assembly.bindings.bind(
        artifact_id="artifact:composition",
        content_sha256=_sha(payload),
        storage_provider_id="artifact.filesystem",
        location=str(content),
    )
    assert binding.content_sha256 == _sha(payload)
    assert assembly.bindings.resolve(binding.artifact_id) == binding

    content.write_bytes(b"tampered")
    with pytest.raises(ArtifactStorageVerificationError) as tampered:
        assembly.bindings.resolve(binding.artifact_id)
    assert tampered.value.code == "CONTENT_SHA256_MISMATCH"


def test_builtin_research_query_composition_wires_portable_sources() -> None:
    datasets = InMemoryDatasetRegistry()
    artifacts = InMemoryArtifactRegistry()
    scopes = InMemoryScopeRegistry()
    dataset_payload = b"dataset-content"
    report_payload = b"report-content"
    datasets.register(
        DatasetVersion(
            DatasetIdentity("evaluation", "v1"),
            PLATFORM_SCOPE,
            _sha(dataset_payload),
        )
    )

    artifacts.put(
        ArtifactRecord(
            artifact_id="report:summary",
            kind=ArtifactKind.REPORT,
            scope=PLATFORM_SCOPE,
            digest=_sha(report_payload),
            producer_component_id="project.analysis",
            media_type="application/json",
        )
    )
    query = compose_builtin_research_result_query(
        datasets=datasets,
        artifacts=artifacts,
        scopes=scopes,
    )
    page = query.query(
        ResearchResultQuery(
            kinds=(ResearchResultKind.DATASET, ResearchResultKind.REPORT),
        )
    )
    assert page.complete is True
    assert page.truncated is False
    assert page.matched_count == 2
    assert {record.reference.kind for record in page.records} == {
        ResearchResultKind.DATASET,
        ResearchResultKind.REPORT,
    }
