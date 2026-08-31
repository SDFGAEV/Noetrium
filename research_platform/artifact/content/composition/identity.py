from __future__ import annotations

from research_platform.artifact.catalog.api import ArtifactNotFound, ArtifactRegistryPort
from research_platform.artifact.content.api import (
    ArtifactContentIdentity,
    ArtifactContentIdentityVerificationError,
    ArtifactStorageBindingNotFound,
    ArtifactStorageBindingPort,
)


def verify_artifact_content_identity(
    identity: ArtifactContentIdentity,
    *,
    artifacts: ArtifactRegistryPort,
    storage: ArtifactStorageBindingPort,
) -> ArtifactContentIdentity:
    """Verify immutable catalog identity and current storage bytes without binding physical location."""

    if type(identity) is not ArtifactContentIdentity:
        raise TypeError("identity must be ArtifactContentIdentity")
    try:
        record = artifacts.get(identity.artifact_id)
    except ArtifactNotFound as exc:
        raise ArtifactContentIdentityVerificationError(
            "ARTIFACT_NOT_FOUND", f"artifact {identity.artifact_id!r} is not registered"
        ) from exc

    if record.artifact_id != identity.artifact_id:
        raise ArtifactContentIdentityVerificationError(
            "CATALOG_IDENTITY_MISMATCH",
            f"catalog returned foreign artifact identity for {identity.artifact_id!r}",
        )
    if record.digest != identity.content_sha256:
        raise ArtifactContentIdentityVerificationError(
            "CATALOG_DIGEST_MISMATCH",
            f"artifact {identity.artifact_id!r} catalog digest does not match claimed content",
        )
    try:
        binding = storage.resolve(identity.artifact_id)
    except ArtifactStorageBindingNotFound as exc:
        raise ArtifactContentIdentityVerificationError(
            "STORAGE_BINDING_NOT_FOUND",
            f"artifact {identity.artifact_id!r} has no verified storage binding",
        ) from exc
    if binding.artifact_id != identity.artifact_id:
        raise ArtifactContentIdentityVerificationError(
            "STORAGE_IDENTITY_MISMATCH",
            f"storage returned foreign artifact identity for {identity.artifact_id!r}",
        )
    if binding.content_sha256 != identity.content_sha256:
        raise ArtifactContentIdentityVerificationError(
            "STORAGE_DIGEST_MISMATCH",
            f"artifact {identity.artifact_id!r} storage digest does not match claimed content",
        )
    return identity


__all__ = ["verify_artifact_content_identity"]
