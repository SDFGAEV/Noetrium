from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
from typing import Iterable

from research_platform.governance.api import (
    RepositorySourceBlob,
    RepositorySourceFailure,
    RepositorySourceFailureKind,
    RepositorySourceIncompleteError,
    RepositorySourceSnapshot,
)


DEFAULT_EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".local", ".server-state", "dist", "build",
})
DEFAULT_EXCLUDED_ROOT_FILES = frozenset({
    "RELEASE_MANIFEST.json",
    "RELEASE_EVIDENCE.json",
    "RELEASE_AUTHORITY.json",
    "DEVELOPMENT_SNAPSHOT_MANIFEST.sha256",
    "DEVELOPMENT_SNAPSHOT_METADATA.json",
    "DEVELOPMENT_ARCHITECTURE_REPORT.json",
})
DEFAULT_GOVERNANCE_SOURCE_SUFFIXES = frozenset({
    ".py", ".js", ".mjs", ".cjs", ".sh", ".bash",
    ".json", ".yaml", ".yml", ".toml",
})


def _failure_path(root: Path, value: object | None) -> str:
    if value in {None, ""}:
        return "."
    candidate = Path(str(value))
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return candidate.as_posix()


class RepositorySourceTree:
    """Deterministic filesystem provider that either yields a complete cut or fails."""

    def __init__(
        self,
        root: Path,
        *,
        include_tests: bool = False,
        excluded_directories: frozenset[str] = DEFAULT_EXCLUDED_DIRECTORIES,
        excluded_root_files: frozenset[str] = DEFAULT_EXCLUDED_ROOT_FILES,
    ) -> None:
        self._root = Path(root).resolve()
        self._include_tests = include_tests
        self._excluded_directories = frozenset(excluded_directories)
        self._excluded_root_files = frozenset(excluded_root_files)
        if any(not name or "/" in name or "\\" in name for name in self._excluded_directories):
            raise ValueError("excluded directory entries must be single non-empty names")
        if any(not name or "/" in name or "\\" in name for name in self._excluded_root_files):
            raise ValueError("excluded root file entries must be single non-empty names")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def include_tests(self) -> bool:
        return self._include_tests

    def _candidate_paths(self, supported: frozenset[str]) -> tuple[Path, ...]:
        candidates: list[Path] = []

        def onerror(exc: OSError) -> None:
            raise RepositorySourceIncompleteError((RepositorySourceFailure(
                RepositorySourceFailureKind.DIRECTORY_WALK,
                _failure_path(self._root, exc.filename),
                type(exc).__name__,
            ),)) from exc

        for directory, dirnames, filenames in os.walk(
            self._root,
            topdown=True,
            onerror=onerror,
        ):
            current = Path(directory)
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in self._excluded_directories
                and not (not self._include_tests and current == self._root and name == "tests")
            )
            candidates.extend(
                current / filename
                for filename in filenames
                if (current / filename).suffix.lower() in supported
                and not (current == self._root and filename in self._excluded_root_files)
            )
        return tuple(sorted(
            candidates,
            key=lambda path: path.relative_to(self._root).as_posix(),
        ))

    def documents(self, *, suffixes: Iterable[str]) -> tuple[RepositorySourceBlob, ...]:
        """Materialize one complete deterministic source cut before exposing any blob.

        Algorithm-Complexity: O(N log N)
        Algorithm-Rationale: Directory discovery is linear in visited entries and the final stable path sort dominates at O(N log N); every selected file is read and decoded exactly once.
        """
        supported = frozenset(str(suffix).lower() for suffix in suffixes)
        if not supported:
            return ()
        blobs: list[RepositorySourceBlob] = []
        for path in self._candidate_paths(supported):
            relative = path.relative_to(self._root).as_posix()
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise RepositorySourceIncompleteError((RepositorySourceFailure(
                    RepositorySourceFailureKind.FILE_READ,
                    relative,
                    type(exc).__name__,
                ),)) from exc
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RepositorySourceIncompleteError((RepositorySourceFailure(
                    RepositorySourceFailureKind.UTF8_DECODE,
                    relative,
                    "invalid utf-8",
                ),)) from exc
            blobs.append(RepositorySourceBlob(
                relative_path=relative,
                suffix=path.suffix.lower(),
                sha256=hashlib.sha256(raw).hexdigest(),
                text=text,
            ))
        return tuple(blobs)

    def snapshot(
        self,
        *,
        suffixes: Iterable[str] = DEFAULT_GOVERNANCE_SOURCE_SUFFIXES,
    ) -> RepositorySourceSnapshot:
        return RepositorySourceSnapshot(self.documents(suffixes=suffixes))

    def index(
        self,
        *,
        suffixes: Iterable[str] = DEFAULT_GOVERNANCE_SOURCE_SUFFIXES,
    ) -> "RepositorySourceIndex":
        return RepositorySourceIndex(self.snapshot(suffixes=suffixes))


class RepositorySourceIndex:
    """Read-only IR over one source cut; Python syntax is parsed once at construction."""

    def __init__(self, snapshot: RepositorySourceSnapshot) -> None:
        self._snapshot = snapshot
        self._by_path = {blob.relative_path: blob for blob in snapshot.blobs}
        trees: dict[str, ast.Module] = {}
        for blob in snapshot.documents(suffixes={".py"}):
            try:
                trees[blob.relative_path] = ast.parse(blob.text, filename=blob.relative_path)
            except SyntaxError as exc:
                raise RepositorySourceIncompleteError((RepositorySourceFailure(
                    RepositorySourceFailureKind.PYTHON_PARSE,
                    blob.relative_path,
                    f"line {exc.lineno or 0}",
                ),)) from exc
        self._python_trees = trees

    @property
    def snapshot(self) -> RepositorySourceSnapshot:
        return self._snapshot

    @property
    def source_digest(self) -> str:
        return self._snapshot.source_digest

    def documents(self, *, suffixes: Iterable[str]) -> tuple[RepositorySourceBlob, ...]:
        return self._snapshot.documents(suffixes=suffixes)

    def _blob(self, relative_path: str, sha256: str | None) -> RepositorySourceBlob:
        try:
            blob = self._by_path[relative_path]
        except KeyError as exc:
            raise KeyError(f"source path is not present in frozen index: {relative_path}") from exc
        if sha256 is not None and blob.sha256 != sha256:
            raise ValueError(f"source identity mismatch for {relative_path}")
        return blob

    def text(self, relative_path: str, *, sha256: str | None = None) -> str:
        return self._blob(relative_path, sha256).text

    def python_tree(self, relative_path: str, *, sha256: str | None = None) -> ast.Module:
        self._blob(relative_path, sha256)
        try:
            return self._python_trees[relative_path]
        except KeyError as exc:
            raise ValueError(f"source is not a Python document: {relative_path}") from exc


__all__ = [
    "DEFAULT_EXCLUDED_DIRECTORIES",
    "DEFAULT_EXCLUDED_ROOT_FILES",
    "DEFAULT_GOVERNANCE_SOURCE_SUFFIXES",
    "RepositorySourceIndex",
    "RepositorySourceTree",
]
