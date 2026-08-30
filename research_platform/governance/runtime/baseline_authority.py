from __future__ import annotations

from research_platform.governance.api import (
    GovernanceBaselineLane,
    RepositorySourceIndexPort,
    repository_source_scope_text_digest,
)


def governance_lane_implementation_digest(
    source_index: RepositorySourceIndexPort,
    lane: GovernanceBaselineLane,
) -> str:
    return repository_source_scope_text_digest(
        source_index,
        path_prefixes=(f"research_platform/governance/{lane.value}",),
    )


__all__ = ["governance_lane_implementation_digest"]
