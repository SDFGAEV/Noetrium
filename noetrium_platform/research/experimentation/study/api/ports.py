from __future__ import annotations

from typing import Protocol

from .contracts import (
    StudyAssignment,
    StudyExecutionUnit,
    StudyMetricAggregate,
    StudyMetricObservation,
    StudyMatrixExecutionReport,
    StudyProtocol,
)
from .plan import ExperimentPlan, VariantBinding


class StudyAssignmentPort(Protocol):
    def assignments(self, protocol: StudyProtocol) -> tuple[StudyAssignment, ...]: ...


class StudyMetricAggregationPort(Protocol):
    def aggregate(
        self,
        protocol: StudyProtocol,
        observations: tuple[StudyMetricObservation, ...],
        expected_assignments: tuple[StudyAssignment, ...],
    ) -> tuple[StudyMetricAggregate, ...]: ...


class StudyUnitExecutionPort(Protocol):
    """Environment-neutral adapter for one complete repetition group."""

    def execute(self, unit: StudyExecutionUnit) -> tuple[StudyMetricObservation, ...]: ...


class StudyVariantExecutionPort(Protocol):
    """Optional adapter used when independent variants are run concurrently."""

    def execute_variant(self, assignment: StudyAssignment) -> StudyMetricObservation: ...


class BoundStudyUnitExecutionPort(Protocol):
    """Environment adapter for a compiled plan and all of its arm bindings."""

    def execute_bound(
        self,
        unit: StudyExecutionUnit,
        bindings: tuple[VariantBinding, ...],
        plan_digest: str,
    ) -> tuple[StudyMetricObservation, ...]: ...


class BoundStudyVariantExecutionPort(Protocol):
    """Compiled-plan counterpart for concurrent variant execution."""

    def execute_bound_variant(
        self,
        assignment: StudyAssignment,
        binding: VariantBinding,
        plan_digest: str,
    ) -> StudyMetricObservation: ...


class StudyMatrixExecutionPort(Protocol):
    """Platform execution seam for one complete frozen study matrix."""

    def execute(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
        adapter: StudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport: ...

    def execute_plan(
        self,
        plan: ExperimentPlan,
        assignments: tuple[StudyAssignment, ...],
        adapter: BoundStudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport: ...


class StudyArtifactPublicationPort(Protocol):
    """Durable publication seam for frozen protocol and derived statistics."""

    def publish_protocol(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
    ) -> str: ...

    def publish_observations(
        self,
        observations: tuple[StudyMetricObservation, ...],
    ) -> str: ...

    def publish_aggregates(
        self,
        aggregates: tuple[StudyMetricAggregate, ...],
    ) -> str: ...


__all__ = [
    "StudyArtifactPublicationPort",
    "StudyAssignmentPort",
    "BoundStudyUnitExecutionPort",
    "StudyMetricAggregationPort",
    "StudyMatrixExecutionPort",
    "StudyUnitExecutionPort",
    "StudyVariantExecutionPort",
    "BoundStudyVariantExecutionPort",
]
