from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ArtifactStorageBinding:
    """Physical storage binding for immutable artifact content."""

    artifact_id: str
    content_sha256: str
    storage_provider_id: str
    location: str
    generation: int

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact storage artifact_id must be non-empty")
        if len(self.content_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.content_sha256
        ):
            raise ValueError("artifact storage content_sha256 must be lowercase SHA-256")
        if not self.storage_provider_id.strip() or not self.location.strip():
            raise ValueError("artifact storage provider/location must be non-empty")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation <= 0:
            raise ValueError("artifact storage generation must be a positive integer")


class ArtifactStorageBindingConflict(RuntimeError):
    pass


class ArtifactStorageBindingCorruptionError(RuntimeError):
    pass


class ArtifactStorageBindingNotFound(KeyError):
    pass


@runtime_checkable
class ArtifactStorageBindingPort(Protocol):
    def bind(
        self,
        *,
        artifact_id: str,
        content_sha256: str,
        storage_provider_id: str,
        location: str,
    ) -> ArtifactStorageBinding: ...

    def resolve(self, artifact_id: str) -> ArtifactStorageBinding: ...

    def relocate(
        self,
        artifact_id: str,
        *,
        expected_generation: int,
        storage_provider_id: str,
        location: str,
    ) -> ArtifactStorageBinding: ...


__all__ = [
    "ArtifactStorageBinding",
    "ArtifactStorageBindingConflict",
    "ArtifactStorageBindingCorruptionError",
    "ArtifactStorageBindingNotFound",
    "ArtifactStorageBindingPort",
]
