from __future__ import annotations

from research_platform.artifact.catalog.api import ArtifactRegistryPort
from research_platform.data.dataset.api import DatasetRegistryPort
from research_platform.data.query.api import ResearchResultQueryPort
from research_platform.data.query.cross.providers import DatasetResearchResultSource
from research_platform.scope.api import ScopeRegistryPort

from .artifact import ArtifactCatalogResearchResultSource
from .default import compose


def compose_builtin_research_result_query(
    *,
    datasets: DatasetRegistryPort,
    artifacts: ArtifactRegistryPort,
    scopes: ScopeRegistryPort,
) -> ResearchResultQueryPort:
    """Wire the built-in portable Dataset and Artifact read projections."""

    return compose(
        (
            DatasetResearchResultSource(datasets, scopes),
            ArtifactCatalogResearchResultSource(artifacts, scopes),
        )
    )


__all__ = ["compose_builtin_research_result_query"]
