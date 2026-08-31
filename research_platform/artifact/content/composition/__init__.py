"""Artifact content composition entrypoints."""

from .acquisition import ArtifactAcquisitionAssembly, compose_artifact_acquisition
from .identity import (
    load_verified_artifact_content_identity,
    resolve_artifact_reference_content_identity,
    verify_artifact_content_identity,
)
from .storage import (
    ArtifactStorageBindingAssembly,
    compose_filesystem_artifact_storage_bindings,
)

__all__ = [
    "ArtifactAcquisitionAssembly",
    "ArtifactStorageBindingAssembly",
    "compose_artifact_acquisition",
    "compose_filesystem_artifact_storage_bindings",
    "load_verified_artifact_content_identity",
    "resolve_artifact_reference_content_identity",
    "verify_artifact_content_identity",
]
