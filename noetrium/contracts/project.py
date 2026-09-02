"""Project identity and manifest contracts for downstream authors.

This module is the stable facade over Portfolio project contracts.
"""

from noetrium_platform.foundation.portfolio.api import (
    PROJECT_MANIFEST_SCHEMA,
    ProjectIdentity,
    ProjectManifest,
    ProjectManifestDecodeError,
    ProjectSpec,
    ProjectToolProvenance,
    decode_project_manifest_bytes,
    decode_project_manifest_document,
    encode_project_manifest,
    project_manifest_document,
)

__all__ = [
    "PROJECT_MANIFEST_SCHEMA", "ProjectIdentity", "ProjectManifest",
    "ProjectManifestDecodeError", "ProjectSpec", "ProjectToolProvenance",
    "decode_project_manifest_bytes", "decode_project_manifest_document",
    "encode_project_manifest", "project_manifest_document",
]
