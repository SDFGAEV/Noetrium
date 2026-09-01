from __future__ import annotations

from research_platform.operator.api import ProjectFacade
from research_platform.operator.runtime.project_experience import LocalProjectExperience


def build_project_facade() -> ProjectFacade:
    """Build the local downstream-project product facade without a service locator."""

    return ProjectFacade(LocalProjectExperience())


__all__ = ["build_project_facade"]
