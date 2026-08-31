from __future__ import annotations

from research_platform.artifact.catalog.api import ArtifactNotFound, ArtifactRegistryPort
from research_platform.artifact.reference.api import (
    ArtifactReference,
    ArtifactReferenceNotFound,
    ArtifactReferencePort,
)
from research_platform.scope.api import ScopeIdentity

from research_platform.artifact.content.api import (
    ArtifactContentIdentity,
    ArtifactContentIdentityVerificationError,
    ArtifactStorageBindingNotFound,
    ArtifactStorageBindingPort,
    ArtifactStoragePlacementVerifierPort,
    ArtifactStorageVerificationError,
)


def verify_artifact_content_identity(
    identity: ArtifactContentIdentity,
    *,
    artifacts: ArtifactRegistryPort,
    storage: ArtifactStorageBindingPort,
    placement_verifier: ArtifactStoragePlacementVerifierPort,
) -> ArtifactContentIdentity:
    """Verify immutable catalog identity and current provider-owned bytes."""

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

    try:
        placement = placement_verifier.verify(
            artifact_id=identity.artifact_id,
            content_sha256=identity.content_sha256,
            storage_provider_id=binding.storage_provider_id,
            location=binding.location,
        )
    except ArtifactStorageVerificationError as exc:
        raise ArtifactContentIdentityVerificationError(
            "STORAGE_PLACEMENT_UNVERIFIED",
            f"artifact {identity.artifact_id!r} placement verification failed with {exc.code}",
        ) from exc
    if (
        placement.artifact_id != identity.artifact_id
        or placement.content_sha256 != identity.content_sha256
        or placement.storage_provider_id != binding.storage_provider_id
        or placement.location != binding.location
    ):
        raise ArtifactContentIdentityVerificationError(
            "STORAGE_PLACEMENT_MISMATCH",
            f"artifact {identity.artifact_id!r} placement verifier returned foreign placement facts",
        )
    return identity


def load_verified_artifact_content_identity(
    artifact_id: str,
    *,
    artifacts: ArtifactRegistryPort,
    storage: ArtifactStorageBindingPort,
    placement_verifier: ArtifactStoragePlacementVerifierPort,
) -> ArtifactContentIdentity:
    """Load a portable content identity from Artifact authority and prove its bytes."""

    try:
        record = artifacts.get(artifact_id)
    except ArtifactNotFound as exc:
        raise ArtifactContentIdentityVerificationError(
            "ARTIFACT_NOT_FOUND", f"artifact {artifact_id!r} is not registered"
        ) from exc
    if record.artifact_id != artifact_id:
        raise ArtifactContentIdentityVerificationError(
            "CATALOG_IDENTITY_MISMATCH",
            f"catalog returned foreign artifact identity for {artifact_id!r}",
        )
    identity = ArtifactContentIdentity(record.artifact_id, record.digest)
    return verify_artifact_content_identity(
        identity,
        artifacts=artifacts,
        storage=storage,
        placement_verifier=placement_verifier,
    )


def resolve_artifact_reference_content_identity(
    reference_id: str,
    scope: ScopeIdentity,
    *,
    references: ArtifactReferencePort,
    artifacts: ArtifactRegistryPort,
    storage: ArtifactStorageBindingPort,
    placement_verifier: ArtifactStoragePlacementVerifierPort,
) -> ArtifactContentIdentity:
    """Snapshot a mutable Artifact reference into a verified immutable content identity."""

    try:
        reference = references.resolve(reference_id, scope)
    except ArtifactReferenceNotFound as exc:
        raise ArtifactContentIdentityVerificationError(
            "ARTIFACT_REFERENCE_NOT_FOUND",
            f"artifact reference {reference_id!r} is not registered for the requested scope",
        ) from exc
    if type(reference) is not ArtifactReference:
        raise ArtifactContentIdentityVerificationError(
            "ARTIFACT_REFERENCE_TYPE_MISMATCH",
            f"artifact reference {reference_id!r} resolved to an untrusted runtime value",
        )
    if reference.reference_id != reference_id or reference.scope != scope:
        raise ArtifactContentIdentityVerificationError(
            "ARTIFACT_REFERENCE_IDENTITY_MISMATCH",
            f"artifact reference {reference_id!r} resolved to foreign reference facts",
        )
    return load_verified_artifact_content_identity(
        reference.artifact_id,
        artifacts=artifacts,
        storage=storage,
        placement_verifier=placement_verifier,
    )


__all__ = [
    "load_verified_artifact_content_identity",
    "resolve_artifact_reference_content_identity",
    "verify_artifact_content_identity",
]
