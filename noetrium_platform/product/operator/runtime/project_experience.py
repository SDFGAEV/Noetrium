from __future__ import annotations

from pathlib import Path

from noetrium_platform.product.operator.api import (
    ProjectCreateReceipt,
    ProjectCreateRequest,
    ProjectDoctorReport,
    ProjectTestReceipt,
)
from noetrium_platform.product.operator.runtime.project_doctor import doctor_project
from noetrium_platform.product.operator.runtime.project_scaffold import create_project
from noetrium_platform.product.operator.runtime.project_testing import test_project


class LocalProjectExperience:
    """Filesystem product adapter; project/domain truth remains producer-owned."""

    def create(self, request: ProjectCreateRequest) -> ProjectCreateReceipt:
        return create_project(request)

    def doctor(self, project_root: Path) -> ProjectDoctorReport:
        return doctor_project(project_root)

    def test(self, project_root: Path) -> ProjectTestReceipt:
        return test_project(project_root)


__all__ = ["LocalProjectExperience", "create_project", "doctor_project", "test_project"]
