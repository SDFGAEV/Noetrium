from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_platform.scope.api import ScopeIdentity


_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class ArtifactContentIdentity:
    """Portable immutable artifact-content identity, independent of aliases and storage placement."""

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

class ArtifactContentIdentityVerificationError(RuntimeError):
    """A claimed immutable content identity cannot be verified against Artifact authority."""

    def __init__(self, code: str, message: str) -> None:
        if type(code) is not str or not code.strip():
            raise ValueError("artifact content identity verification code must be non-empty")
        self.code = code
        super().__init__(f"artifact content identity verification failed [{code}]: {message}")


@runtime_checkable
class ArtifactContentIdentityResolverPort(Protocol):
    """Read-only Artifact authority for verified immutable content identities."""

    def verify(self, identity: ArtifactContentIdentity) -> ArtifactContentIdentity: ...

    def load(self, artifact_id: str) -> ArtifactContentIdentity: ...

    def snapshot_reference(
        self,
        reference_id: str,
        scope: ScopeIdentity,
    ) -> ArtifactContentIdentity: ...


__all__ = [
    "ArtifactContentIdentity",
    "ArtifactContentIdentityResolverPort",
    "ArtifactContentIdentityVerificationError",
]
