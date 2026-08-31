"""Canonical project contracts are owned by ``research_platform.portfolio.api``.

This leaf re-exports that single authority so ``portfolio.project`` does not
create a competing manifest/identity model.
"""

from research_platform.portfolio.api import (
    PROJECT_MANIFEST_SCHEMA,
    ProjectCapabilityRequirement,
    ProjectConfigurationReference,
    ProjectIdentity,
    ProjectManifest,
    ProjectManifestDecodeError,
    ProjectManifestFacet,
    ProjectManifestFacetChange,
    ProjectManifestFacetDiff,
    ProjectManifestIdentityFacets,
    ProjectProviderBinding,
    ProjectMethodRequirement,
    ProjectRequirementCardinality,
    ProjectSpec,
    ProjectToolProvenance,
    decode_project_manifest_bytes,
    decode_project_manifest_document,
    diff_project_manifest_facets,
    encode_project_manifest,
    project_manifest_document,
    project_manifest_identity_facets,
)

__all__ = [
    "PROJECT_MANIFEST_SCHEMA",
    "ProjectCapabilityRequirement",
    "ProjectConfigurationReference",
    "ProjectIdentity",
    "ProjectManifest",
    "ProjectManifestDecodeError",
    "ProjectManifestFacet",
    "ProjectManifestFacetChange",
    "ProjectManifestFacetDiff",
    "ProjectManifestIdentityFacets",
    "ProjectProviderBinding",
    "ProjectMethodRequirement",
    "ProjectRequirementCardinality",
    "ProjectSpec",
    "ProjectToolProvenance",
    "decode_project_manifest_bytes",
    "decode_project_manifest_document",
    "diff_project_manifest_facets",
    "encode_project_manifest",
    "project_manifest_document",
    "project_manifest_identity_facets",
]
