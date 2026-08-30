from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

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
        (f"research_platform.governance.{lane.value}",),
    )


def governance_baseline_semantic_digest(
    *,
    lane: GovernanceBaselineLane,
    source_revision: str,
    source_digest: str,
    analyzer_revision: str,
    analyzer_implementation_digest: str,
    blocker_fingerprints: Iterable[str],
) -> str:
    payload = {
        "lane": lane.value,
        "source_revision": source_revision,
        "source_digest": source_digest,
        "analyzer_revision": analyzer_revision,
        "analyzer_implementation_digest": analyzer_implementation_digest,
        "blocker_fingerprints": sorted(str(item) for item in blocker_fingerprints),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "governance_baseline_semantic_digest",
    "governance_lane_implementation_digest",
]
