"""Canonical project contracts are owned by ``research_platform.portfolio.api``.

This leaf re-exports that single authority so ``portfolio.project`` does not
create a competing manifest/identity model.
"""

from research_platform.portfolio.api import (
    PROJECT_MANIFEST_SCHEMA,
    PROJECT_TEMPLATE_REVISION,
    ProjectCapabilityRequirement,
    ProjectConfigurationReference,
    ProjectIdentity,
    ProjectManifest,
    ProjectManifestDecodeError,
    ProjectProviderBinding,
    ProjectMethodRequirement,
    ProjectRequirementCardinality,
    ProjectSpec,
    ProjectToolProvenance,
    decode_project_manifest_bytes,
    decode_project_manifest_document,
    encode_project_manifest,
    project_manifest_document,
)

__all__ = [
    "PROJECT_MANIFEST_SCHEMA",
    "PROJECT_TEMPLATE_REVISION",
    "ProjectCapabilityRequirement",
    "ProjectConfigurationReference",
    "ProjectIdentity",
    "ProjectManifest",
    "ProjectManifestDecodeError",
    "ProjectProviderBinding",
    "ProjectMethodRequirement",
    "ProjectRequirementCardinality",
    "ProjectSpec",
    "ProjectToolProvenance",
    "decode_project_manifest_bytes",
    "decode_project_manifest_document",
    "encode_project_manifest",
    "project_manifest_document",
]
