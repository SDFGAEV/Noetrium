from __future__ import annotations

from dataclasses import dataclass

import pytest

from research_platform.artifact.catalog.api import ArtifactNotFound
from research_platform.artifact.content.api import (
    ArtifactContentIdentity,
    ArtifactContentIdentityVerificationError,
    ArtifactStorageBinding,
    ArtifactStorageBindingNotFound,
)
from research_platform.artifact.content.composition import verify_artifact_content_identity


DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


@dataclass(frozen=True)
class _Record:
    artifact_id: str
    digest: str


class _Artifacts:
    def __init__(self, digest: str | None) -> None:
        self.digest = digest

    def get(self, artifact_id: str) -> _Record:
        if self.digest is None:
            raise ArtifactNotFound(artifact_id)
        return _Record(artifact_id, self.digest)


class _Storage:
    def __init__(self, binding: ArtifactStorageBinding | None) -> None:
        self.binding = binding

    def resolve(self, artifact_id: str) -> ArtifactStorageBinding:
        if self.binding is None:
            raise ArtifactStorageBindingNotFound(artifact_id)
        return self.binding


def _binding(*, digest: str = DIGEST, location: str = "A:/artifact.bin", generation: int = 1) -> ArtifactStorageBinding:
    return ArtifactStorageBinding(
        artifact_id="artifact-1",
        content_sha256=digest,
        storage_provider_id="artifact.filesystem",
        location=location,
        generation=generation,
    )


def test_artifact_content_identity_is_portable_and_minimal() -> None:
    identity = ArtifactContentIdentity("artifact-1", DIGEST)
    assert identity.artifact_id == "artifact-1"
    assert identity.content_sha256 == DIGEST
    assert not hasattr(identity, "location")
    assert not hasattr(identity, "reference_id")
    assert not hasattr(identity, "generation")

    with pytest.raises(ValueError):
        ArtifactContentIdentity("", DIGEST)
    with pytest.raises(ValueError):
        ArtifactContentIdentity("artifact-1", "A" * 64)


def test_artifact_content_identity_survives_storage_relocation() -> None:
    identity = ArtifactContentIdentity("artifact-1", DIGEST)
    artifacts = _Artifacts(DIGEST)

    first = verify_artifact_content_identity(
        identity,
        artifacts=artifacts,
        storage=_Storage(_binding(location="A:/artifact.bin", generation=1)),
    )
    relocated = verify_artifact_content_identity(
        identity,
        artifacts=artifacts,
        storage=_Storage(_binding(location="B:/archive/artifact.bin", generation=2)),
    )

    assert first is identity
    assert relocated is identity


def test_artifact_content_identity_fails_closed_on_catalog_or_storage_drift() -> None:
    identity = ArtifactContentIdentity("artifact-1", DIGEST)

    with pytest.raises(ArtifactContentIdentityVerificationError) as missing_artifact:
        verify_artifact_content_identity(identity, artifacts=_Artifacts(None), storage=_Storage(_binding()))
    assert missing_artifact.value.code == "ARTIFACT_NOT_FOUND"

    with pytest.raises(ArtifactContentIdentityVerificationError) as catalog_drift:
        verify_artifact_content_identity(identity, artifacts=_Artifacts(OTHER_DIGEST), storage=_Storage(_binding()))
    assert catalog_drift.value.code == "CATALOG_DIGEST_MISMATCH"


    with pytest.raises(ArtifactContentIdentityVerificationError) as missing_storage:
        verify_artifact_content_identity(identity, artifacts=_Artifacts(DIGEST), storage=_Storage(None))
    assert missing_storage.value.code == "STORAGE_BINDING_NOT_FOUND"

    with pytest.raises(ArtifactContentIdentityVerificationError) as storage_drift:
        verify_artifact_content_identity(
            identity,
            artifacts=_Artifacts(DIGEST),
            storage=_Storage(_binding(digest=OTHER_DIGEST)),
        )
    assert storage_drift.value.code == "STORAGE_DIGEST_MISMATCH"


class _ForeignArtifacts(_Artifacts):
    def get(self, artifact_id: str) -> _Record:
        return _Record("artifact-foreign", DIGEST)


def test_artifact_content_identity_rejects_foreign_identity_impostors() -> None:
    identity = ArtifactContentIdentity("artifact-1", DIGEST)

    with pytest.raises(ArtifactContentIdentityVerificationError) as catalog_impostor:
        verify_artifact_content_identity(identity, artifacts=_ForeignArtifacts(DIGEST), storage=_Storage(_binding()))
    assert catalog_impostor.value.code == "CATALOG_IDENTITY_MISMATCH"

    foreign_binding = ArtifactStorageBinding(
        artifact_id="artifact-foreign",
        content_sha256=DIGEST,
        storage_provider_id="artifact.filesystem",
        location="A:/artifact.bin",
        generation=1,
    )
    with pytest.raises(ArtifactContentIdentityVerificationError) as storage_impostor:
        verify_artifact_content_identity(identity, artifacts=_Artifacts(DIGEST), storage=_Storage(foreign_binding))
    assert storage_impostor.value.code == "STORAGE_IDENTITY_MISMATCH"
