"""Explicit assembly for Platform execution facades."""

from noetrium_platform.research.experimentation.api import ExperimentRunner
from noetrium_platform.research.experimentation.study.runtime import StudyMatrixExecutor
from noetrium_platform.research.experimentation.study.runtime.protocol import BasicStudyMetricAggregator
from noetrium_platform.research.experimentation.study.runtime.protocol import DeterministicStudyAssignment
from noetrium_platform.foundation.kernel.concurrency.api import TaskGroupPort


def build_experiment_runner(task_group: TaskGroupPort | None = None) -> ExperimentRunner:
    executor = StudyMatrixExecutor(
        BasicStudyMetricAggregator(),
        DeterministicStudyAssignment(),
        task_group,
    )
    return ExperimentRunner(executor)


__all__ = ["build_experiment_runner"]
