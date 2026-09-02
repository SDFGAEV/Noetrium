"""Explicit assembly for Platform execution facades."""

from research_platform.experimentation.api import ExperimentRunner
from research_platform.experimentation.study.runtime import StudyMatrixExecutor
from research_platform.experimentation.study.runtime.protocol import BasicStudyMetricAggregator
from research_platform.experimentation.study.runtime.protocol import DeterministicStudyAssignment
from research_platform.platform.concurrency.api import TaskGroupPort


def build_experiment_runner(task_group: TaskGroupPort | None = None) -> ExperimentRunner:
    executor = StudyMatrixExecutor(
        BasicStudyMetricAggregator(),
        DeterministicStudyAssignment(),
        task_group,
    )
    return ExperimentRunner(executor)


__all__ = ["build_experiment_runner"]
