from __future__ import annotations

from threading import RLock

from noetrium_platform.foundation.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeRegistryPort
from noetrium_platform.foundation.portfolio.api import ProgramSpec, ProjectManifest, WorkspaceSpec


class PortfolioConflict(RuntimeError):
    pass


class PortfolioNotFound(KeyError):
    pass


class InMemoryPortfolioCatalog:
    """Thread-safe portfolio metadata authority; Scope owns hierarchy truth."""

    def __init__(self, scopes: ScopeRegistryPort) -> None:
        self._scopes = scopes
        self._workspaces: dict[str, WorkspaceSpec] = {}
        self._programs: dict[str, ProgramSpec] = {}
        self._projects: dict[str, ProjectManifest] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_put(store: dict[str, object], key: str, value: object) -> None:
        current = store.get(key)
        if current is not None and current != value:
            raise PortfolioConflict(f"identity already registered with different content: {key}")

    def register_workspace(self, spec: WorkspaceSpec) -> None:
        with self._lock:
            self._validate_put(self._workspaces, spec.workspace_id, spec)
            self._scopes.register(spec.scope, PLATFORM_SCOPE)
            self._workspaces[spec.workspace_id] = spec

    def register_program(self, spec: ProgramSpec) -> None:
        with self._lock:
            workspace = self._workspaces.get(spec.workspace_id)
            if workspace is None:
                raise PortfolioNotFound(f"workspace not registered: {spec.workspace_id}")
            self._validate_put(self._programs, spec.program_id, spec)
            self._scopes.register(spec.scope, workspace.scope)
            self._programs[spec.program_id] = spec

    def register_project(self, manifest: ProjectManifest) -> None:
        spec = manifest.project
        with self._lock:
            program = self._programs.get(spec.program_id)
            if program is None:
                raise PortfolioNotFound(f"program not registered: {spec.program_id}")
            self._validate_put(self._projects, spec.project_id, manifest)
            self._scopes.register(spec.scope, program.scope)
            self._projects[spec.project_id] = manifest

    def workspace(self, workspace_id: str) -> WorkspaceSpec:
        with self._lock:
            try:
                return self._workspaces[workspace_id]
            except KeyError as exc:
                raise PortfolioNotFound(workspace_id) from exc

    def program(self, program_id: str) -> ProgramSpec:
        with self._lock:
            try:
                return self._programs[program_id]
            except KeyError as exc:
                raise PortfolioNotFound(program_id) from exc

    def project(self, project_id: str) -> ProjectManifest:
        with self._lock:
            try:
                return self._projects[project_id]
            except KeyError as exc:
                raise PortfolioNotFound(project_id) from exc

    def projects(self, *, program_id: str | None = None) -> tuple[ProjectManifest, ...]:
        with self._lock:
            rows = tuple(self._projects.values())
        if program_id is not None:
            rows = tuple(row for row in rows if row.project.program_id == program_id)
        return tuple(sorted(rows, key=lambda row: row.project.project_id))


__all__ = ["InMemoryPortfolioCatalog", "PortfolioConflict", "PortfolioNotFound"]
