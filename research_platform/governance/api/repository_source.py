from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol


class RepositorySourceFailureKind(str, Enum):
    DIRECTORY_WALK = "directory_walk"
    FILE_READ = "file_read"
    UTF8_DECODE = "utf8_decode"
    PYTHON_PARSE = "python_parse"
    CONFIG_PARSE = "config_parse"
    GIT_RESOLUTION = "git_resolution"
    GIT_OBJECT = "git_object"


@dataclass(frozen=True, slots=True)
class RepositorySourceFailure:
    kind: RepositorySourceFailureKind
    relative_path: str
    detail: str


class RepositorySourceIncompleteError(RuntimeError):
    """Raised when a complete, internally consistent repository source cut cannot be built."""

    def __init__(self, failures: Iterable[RepositorySourceFailure]) -> None:
        self.failures = tuple(failures)
        if not self.failures:
            raise ValueError("repository source failure must contain at least one diagnostic")
        joined = "; ".join(
            f"{item.kind.value}:{item.relative_path}:{item.detail}" for item in self.failures
        )
        super().__init__(f"governance source snapshot incomplete: {joined}")


@dataclass(frozen=True, slots=True)
class RepositorySourceBlob:
    """Decoded repository source with identity bound to exact filesystem bytes."""

    relative_path: str
    suffix: str
    sha256: str
    text: str


class RepositorySourcePort(Protocol):
    """Read-only source discovery contract; scoring semantics stay with consumers."""

    def documents(self, *, suffixes: Iterable[str]) -> Iterable[RepositorySourceBlob]: ...


class RepositorySourceIndexPort(RepositorySourcePort, Protocol):
    """One immutable source cut plus the canonical parsed Python IR for that cut."""

    @property
    def source_digest(self) -> str: ...

    @property
    def source_authority(self) -> str: ...

    @property
    def source_revision(self) -> str | None: ...

    def text(self, relative_path: str, *, sha256: str | None = None) -> str: ...

    def python_tree(self, relative_path: str, *, sha256: str | None = None) -> ast.Module: ...


@dataclass(frozen=True, slots=True)
class RepositorySourceSnapshot:
    """Immutable source cut for multiple governance analyses over identical bytes."""

    blobs: tuple[RepositorySourceBlob, ...]

    def __post_init__(self) -> None:
        paths = tuple(blob.relative_path for blob in self.blobs)
        if paths != tuple(sorted(paths)):
            raise ValueError("repository source snapshot must be path-sorted")
        if len(paths) != len(set(paths)):
            raise ValueError("repository source snapshot contains duplicate paths")

    @property
    def source_digest(self) -> str:
        digest = hashlib.sha256()
        for blob in self.blobs:
            digest.update(blob.relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(blob.suffix.encode("ascii"))
            digest.update(b"\0")
            digest.update(blob.sha256.encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()

    def documents(self, *, suffixes: Iterable[str]) -> tuple[RepositorySourceBlob, ...]:
        supported = frozenset(str(suffix).lower() for suffix in suffixes)
        if not supported:
            return ()
        return tuple(blob for blob in self.blobs if blob.suffix in supported)


__all__ = [
    "RepositorySourceBlob",
    "RepositorySourceFailure",
    "RepositorySourceFailureKind",
    "RepositorySourceIncompleteError",
    "RepositorySourceIndexPort",
    "RepositorySourcePort",
    "RepositorySourceSnapshot",
]
