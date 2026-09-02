from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from noetrium_platform.research.experimentation.run.api.spec import ExperimentRunSpec
from noetrium_platform.research.experimentation.study.api import (
    BoundStudyUnitExecutionPort,
    ExperimentPlan,
    StudyMatrixExecutionReport,
    StudyProtocol,
    StudyUnitExecutionPort,
)


@dataclass(frozen=True, slots=True)
class ExperimentRunResult:
    """Run-owned envelope around the direct Study child result."""

    run_spec_digest: str
    protocol_digest: str
    study_report: StudyMatrixExecutionReport
    plan_digest: str | None = None
    binding_digest: str | None = None

    def __post_init__(self) -> None:
        if len(self.run_spec_digest) != 64 or len(self.protocol_digest) != 64:
            raise ValueError("experiment run result identities must be SHA-256 digests")
        if self.study_report.protocol_digest != self.protocol_digest:
            raise ValueError("experiment run result protocol digest is inconsistent")
        if self.plan_digest is not None and self.study_report.plan_digest != self.plan_digest:
            raise ValueError("experiment run result plan digest is inconsistent")
        if self.binding_digest is not None and self.study_report.binding_digest != self.binding_digest:
            raise ValueError("experiment run result binding digest is inconsistent")
        if self.plan_digest is not None and self.binding_digest is None:
            raise ValueError("experiment run result plan digest requires a binding digest")


class ExperimentRunExecutionPort(Protocol):
    """Run-layer parent port for one frozen scientific study.

    The run system owns the lifecycle of the generic study execution.  The
    injected unit adapter owns only environment realization; it may be MC,
    closed-world, simulator-backed, or another future environment.
    """

    def execute(
        self,
        *,
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol | None = None,
        plan: ExperimentPlan | None = None,
        unit_adapter: StudyUnitExecutionPort | BoundStudyUnitExecutionPort,
    ) -> ExperimentRunResult: ...


__all__ = ["ExperimentRunExecutionPort", "ExperimentRunResult"]
