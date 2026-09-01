from __future__ import annotations

from research_platform.experimentation.run.api import ExperimentRunExecutionPort, RunArtifactStorePort
from research_platform.experimentation.run.runtime import ExperimentRunApplication
from research_platform.experimentation.study.composition import (
    build_default_study_protocol_services,
    build_run_study_publication,
)
from research_platform.experimentation.study.runtime import StudyMatrixExecutor


def build_default_experiment_run_application(
    artifacts: RunArtifactStorePort,
) -> ExperimentRunExecutionPort:
    """Compose the run parent with its direct Study child implementations."""

    assignment_port, aggregation_port = build_default_study_protocol_services()
    return ExperimentRunApplication(
        assignments=assignment_port,
        matrix=StudyMatrixExecutor(aggregation_port),
        publication=build_run_study_publication(artifacts),
    )


__all__ = ["build_default_experiment_run_application"]
