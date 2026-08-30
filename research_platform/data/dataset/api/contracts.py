from __future__ import annotations

from dataclasses import dataclass

from research_platform.scope.api import ScopeIdentity


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    dataset_id: str
    version: str

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.version.strip():
            raise ValueError("dataset identity/version must be non-empty")

    @property
    def key(self) -> str:
        return f"{self.dataset_id}@{self.version}"


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    identity: DatasetIdentity
    scope: ScopeIdentity
    digest: str
    location: str
    schema_ref: str | None = None
    parent_versions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Validate complete variable-cardinality dataset authority before acceptance.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: N is parent, tag, and metadata cardinality; tail corruption and duplicate authority must fail closed, which requires complete traversal.
        """
        if len(self.digest) != 64 or any(char not in "0123456789abcdef" for char in self.digest):
            raise ValueError("dataset digest must be lowercase SHA-256")
        if not self.location.strip():
            raise ValueError("dataset location must be non-empty")
        if self.schema_ref is not None and not self.schema_ref.strip():
            raise ValueError("dataset schema_ref must be non-empty when present")
        for name, values in (("parent_versions", self.parent_versions), ("tags", self.tags)):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError(f"dataset {name} must be non-empty and unique")
        keys = [key for key, _ in self.metadata]
        if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("dataset metadata keys must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class DatasetQuery:
    dataset_id: str | None = None
    scope: ScopeIdentity | None = None
    tag: str | None = None
    limit: int = 1000

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or not 1 <= self.limit <= 10_000:
            raise ValueError("dataset query limit must be an integer in [1, 10000]")


__all__ = ["DatasetIdentity", "DatasetQuery", "DatasetVersion"]
