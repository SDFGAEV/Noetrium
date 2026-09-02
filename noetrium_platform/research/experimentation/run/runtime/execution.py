from __future__ import annotations

from noetrium_platform.research.experimentation.run.api import ExperimentRunExecutionPort, ExperimentRunResult
from noetrium_platform.research.experimentation.run.api.spec import ExperimentRunSpec
from noetrium_platform.research.experimentation.study.api import (
    BoundStudyUnitExecutionPort,
    ExperimentPlan,
    StudyArtifactPublicationPort,
    StudyAssignmentPort,
    StudyMatrixExecutionPort,
    StudyMatrixExecutionReport,
    StudyProtocol,
    StudyUnitExecutionPort,
)


def _require_resolved_protocol(value: StudyProtocol | None) -> StudyProtocol:
    if value is None:
        raise RuntimeError("experiment run protocol resolution failed")
    return value


class ExperimentRunApplication(ExperimentRunExecutionPort):
    """The generic run parent over the direct Study child.

    This is intentionally the only run-level owner of assignment expansion,
    study execution and scientific artifact publication.  Environment roots
    receive this narrow port; they do not each compose a second matrix loop.
    """

    def __init__(
        self,
        *,
        assignments: StudyAssignmentPort,
        matrix: StudyMatrixExecutionPort,
        publication: StudyArtifactPublicationPort,
    ) -> None:
        self._assignments = assignments
        self._matrix = matrix
        self._publication = publication

    def execute(
        self,
        *,
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol | None = None,
        plan: ExperimentPlan | None = None,
        unit_adapter: StudyUnitExecutionPort | BoundStudyUnitExecutionPort,
    ) -> ExperimentRunResult:
        if (protocol is None) == (plan is None):
            raise ValueError("experiment run requires exactly one protocol or compiled plan")
        active_protocol = _require_resolved_protocol(
            plan.protocol if plan is not None else protocol
        )
        self._validate_run_identity(run_spec, active_protocol)
        assignments = self._assignments.assignments(active_protocol)
        if not assignments:
            raise ValueError("experiment run requires at least one frozen study assignment")
        self._publication.publish_protocol(active_protocol, assignments)
        if plan is None:
            report = self._matrix.execute(active_protocol, assignments, unit_adapter)
        else:
            report = self._matrix.execute_plan(plan, assignments, unit_adapter)
        self._publication.publish_observations(report.observations)
        self._publication.publish_aggregates(report.aggregates)
        return ExperimentRunResult(
            run_spec_digest=run_spec.identity_digest(),
            protocol_digest=active_protocol.protocol_digest,
            study_report=report,
            plan_digest=plan.plan_digest if plan is not None else None,
            binding_digest=plan.binding_digest if plan is not None else None,
        )

    @staticmethod
    def _validate_run_identity(
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol,
    ) -> None:
        if run_spec.study_id != protocol.study_id:
            raise ValueError("experiment run specification belongs to another study")
        if run_spec.task_manifest_digest != protocol.task_manifest_digest:
            raise ValueError("experiment run task digest does not match study protocol")
        if run_spec.seed_schedule_digest != protocol.seed_schedule_digest:
            raise ValueError("experiment run seed digest does not match study protocol")
        if run_spec.repetitions != protocol.repetitions:
            raise ValueError("experiment run repetition count does not match study protocol")


__all__ = ["ExperimentRunApplication"]
