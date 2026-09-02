"""Stable product facade for applications built on Noetrium."""

from noetrium_platform.api import (
    ProjectTestStage,
    ProjectTestStageReceipt,
    ResearchAction,
    ResearchApplicationPort,
    ResearchFacade,
    ResearchOperationFailure,
    ResearchRequest,
    ResearchResult,
)
from noetrium_platform.product.operator.runtime.run_control_application import (
    bind_run_control_application,
)

__all__ = [
    "ProjectTestStage", "ProjectTestStageReceipt", "ResearchAction",
    "ResearchApplicationPort", "ResearchFacade", "ResearchOperationFailure",
    "ResearchRequest", "ResearchResult", "bind_run_control_application",
]
