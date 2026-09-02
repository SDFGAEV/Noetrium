from __future__ import annotations

from noetrium_platform.product.operator.api import ProjectFacade
from noetrium_platform.product.operator.runtime.project_experience import LocalProjectExperience


def build_project_facade() -> ProjectFacade:
    """Build the local downstream-project product facade without a service locator."""

    return ProjectFacade(LocalProjectExperience())


__all__ = ["build_project_facade"]
