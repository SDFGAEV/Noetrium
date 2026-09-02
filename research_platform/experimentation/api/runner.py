"""Public execution facade for compiled research plans."""

from __future__ import annotations

from typing import Protocol

from research_platform.experimentation.study.api import (
    BoundStudyUnitExecutionPort,
    ExperimentPlan,
    StudyAssignment,
    StudyMatrixExecutionReport,
)


class ExperimentPlanExecutionPort(Protocol):
    def execute_plan(
        self,
        plan: ExperimentPlan,
        assignments: tuple[StudyAssignment, ...],
        adapter: BoundStudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport: ...


class ExperimentRunnerPort(Protocol):
    def execute(
        self, plan: ExperimentPlan, adapter: BoundStudyUnitExecutionPort
    ) -> StudyMatrixExecutionReport: ...


class ExperimentRunner:
    """Execute a frozen plan through one injected executor."""

    def __init__(self, executor: ExperimentPlanExecutionPort) -> None:
        if not callable(getattr(executor, "execute_plan", None)):
            raise TypeError("experiment runner requires an injected plan executor")
        self._executor = executor

    def execute(
        self, plan: ExperimentPlan, adapter: BoundStudyUnitExecutionPort
    ) -> StudyMatrixExecutionReport:
        if type(plan) is not ExperimentPlan:
            raise TypeError("experiment runner requires ExperimentPlan")
        plan.assert_consistent()
        return self._executor.execute_plan(plan, plan.assignments, adapter)


__all__ = ["ExperimentPlanExecutionPort", "ExperimentRunner", "ExperimentRunnerPort"]
