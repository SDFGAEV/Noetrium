from __future__ import annotations

from dataclasses import dataclass

_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class ArtifactContentIdentity:
    """Portable immutable Artifact identity shared by catalog, data, lineage and evidence."""

    artifact_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not str or not self.artifact_id.strip():
            raise ValueError("artifact content identity artifact_id must be non-empty")
        if (
            type(self.content_sha256) is not str
            or len(self.content_sha256) != 64
            or any(char not in _HEX for char in self.content_sha256)
        ):
            raise ValueError("artifact content identity content_sha256 must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class SystemIdentity:
    id: str
    version: str = "1"
    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("system id must be non-empty")
        if not self.version.strip():
            raise ValueError("system version must be non-empty")

@dataclass(frozen=True, slots=True)
class SystemSpec:
    identity: SystemIdentity
    purpose: str
    children: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("system purpose must be non-empty")
