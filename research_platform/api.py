"""Canonical topology-hiding product API for common Research Platform control."""

from research_platform.operator.api import (
    ProjectCreateReceipt,
    ProjectDoctorReport,
    ProjectFacade,
    ProjectTestReceipt,
    ResearchAction,
    ResearchApplicationPort,
    ResearchFacade,
    ResearchOperationFailure,
    ResearchRequest,
    ResearchResult,
)
from research_platform.operator.composition.project_experience import build_project_facade
from research_platform.operator.runtime.run_control_application import bind_run_control_application

__all__ = [
    "ProjectCreateReceipt",
    "ProjectDoctorReport",
    "ProjectFacade",
    "ProjectTestReceipt",
    "ResearchAction",
    "ResearchApplicationPort",
    "ResearchFacade",
    "ResearchOperationFailure",
    "ResearchRequest",
    "ResearchResult",
    "bind_run_control_application",
    "build_project_facade",
]
