from __future__ import annotations

from research_platform.data.query.api import ResearchResultSourcePort
from research_platform.data.query.cross.runtime import CrossAuthorityResearchResultQuery


def compose(
    sources: tuple[ResearchResultSourcePort, ...],
) -> CrossAuthorityResearchResultQuery:
    """Compose only read-side producer projections; no handler or mutable query state exists."""

    return CrossAuthorityResearchResultQuery(sources)


__all__ = ["compose"]
