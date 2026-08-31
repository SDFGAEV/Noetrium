from __future__ import annotations

from pathlib import Path

from research_platform.model.catalog.revision.api import ModelRevisionAuthorityPort
from research_platform.model.catalog.revision.providers import SQLiteModelRevisionAuthority


def sqlite_revision_authority(path: str | Path) -> ModelRevisionAuthorityPort:
    """Compose the durable local authority for one logical model revision lineage."""
    return SQLiteModelRevisionAuthority(path)


__all__ = ["sqlite_revision_authority"]
