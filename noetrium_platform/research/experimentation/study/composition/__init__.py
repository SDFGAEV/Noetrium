from ..runtime import BasicStudyMetricAggregator, DeterministicStudyAssignment
from ..providers import RunArtifactStudyPublication
from noetrium_platform.research.experimentation.run.api import RunArtifactStorePort
from .research_result_source import StudyResearchResultSource


def build_default_study_protocol_services() -> tuple[DeterministicStudyAssignment, BasicStudyMetricAggregator]:
    return DeterministicStudyAssignment(), BasicStudyMetricAggregator()


def build_run_study_publication(artifacts: RunArtifactStorePort) -> RunArtifactStudyPublication:
    return RunArtifactStudyPublication(artifacts)


__all__ = [
    "StudyResearchResultSource",
    "build_default_study_protocol_services",
    "build_run_study_publication",
]
