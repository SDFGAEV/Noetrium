from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from research_platform.portfolio.api import ProjectIdentity

PROJECT_TEMPLATE_REVISION = "research-platform.project-template.v1"


class ProjectDoctorDisposition(StrEnum):
    PASS = "pass"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ProjectCreateRequest:
    project_id: str
    version: str
    destination: Path
    program_id: str = "standalone"

    def __post_init__(self) -> None:
        ProjectIdentity(self.project_id, self.version)
        if not isinstance(self.destination, Path):
            raise TypeError("project destination must be a pathlib.Path")


@dataclass(frozen=True, slots=True)
class ProjectCreateReceipt:
    project_id: str
    version: str
    program_id: str
    destination: str
    template_revision: str
    manifest_path: str
    manifest_semantic_digest: str
    generated_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectDoctorCheck:
    check_id: str
    disposition: ProjectDoctorDisposition
    summary: str
    remediation: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.summary.strip():
            raise ValueError("project doctor check identity/summary are required")
        if self.disposition is ProjectDoctorDisposition.BLOCKED and not self.remediation.strip():
            raise ValueError("blocked project doctor checks require remediation")


@dataclass(frozen=True, slots=True)
class ProjectDoctorReport:
    project_root: str
    template_revision: str | None
    checks: tuple[ProjectDoctorCheck, ...]

    @property
    def ready(self) -> bool:
        return bool(self.checks) and all(
            check.disposition is ProjectDoctorDisposition.PASS for check in self.checks
        )


@dataclass(frozen=True, slots=True)
class ProjectTestReceipt:
    project_root: str
    command: tuple[str, ...]
    exit_code: int

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


class ProjectExperiencePort(Protocol):
    """Injected product authority for downstream project experience operations."""
    def create(self, request: ProjectCreateRequest) -> ProjectCreateReceipt: ...

    def doctor(self, project_root: Path) -> ProjectDoctorReport: ...

    def test(self, project_root: Path) -> ProjectTestReceipt: ...


class ProjectFacade:
    """Topology-hiding Python facade over an explicitly injected project experience port."""

    def __init__(self, experience: ProjectExperiencePort) -> None:
        for name in ("create", "doctor", "test"):
            if not callable(getattr(experience, name, None)):
                raise TypeError(f"project experience must implement {name}()")
        self._experience = experience

    def create(
        self,
        project_id: str,
        version: str,
        destination: Path,
        *,
        program_id: str = "standalone",
    ) -> ProjectCreateReceipt:
        return self._experience.create(
            ProjectCreateRequest(project_id, version, destination, program_id)
        )

    def doctor(self, project_root: Path) -> ProjectDoctorReport:
        return self._experience.doctor(project_root)

    def test(self, project_root: Path) -> ProjectTestReceipt:
        return self._experience.test(project_root)


__all__ = [
    "PROJECT_TEMPLATE_REVISION",
    "ProjectCreateReceipt",
    "ProjectCreateRequest",
    "ProjectDoctorCheck",
    "ProjectDoctorDisposition",
    "ProjectDoctorReport",
    "ProjectExperiencePort",
    "ProjectFacade",
    "ProjectTestReceipt",
]
