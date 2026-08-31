from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pytest

from research_platform.participant.method.api import (
    MethodIdentity,
    MethodProgramIdentity,
    MethodRuntimeIdentity,
    ResearchMethodProgram,
)
from research_platform.platform.kernel import ExecutionContext


@dataclass(frozen=True, slots=True)
class PaperTask:
    task_id: str
    threshold: float


@dataclass(frozen=True, slots=True)
class VectorObservation:
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PaperDecision:
    accepted: bool
    score: float
    trace: tuple[str, ...]

class ScorePort(Protocol):
    def score(self, values: tuple[float, ...]) -> float: ...


class MeanScore:
    def score(self, values: tuple[float, ...]) -> float:
        return sum(values) / len(values)


class PaperOnlyControlGraph:
    def __init__(self, scorer: ScorePort, configuration_digest: str) -> None:
        self._scorer = scorer
        self._program_identity = MethodProgramIdentity(
            MethodIdentity("paper-only-control", "1", "abi1", "schema1", "a" * 64),
            configuration_digest,
        )

    @property
    def program_identity(self) -> MethodProgramIdentity:
        return self._program_identity

    def run(
        self,
        *,
        task: PaperTask,
        input_value: VectorObservation,
        context: ExecutionContext,
    ) -> PaperDecision:
        score = self._scorer.score(input_value.values)
        trace = (context.run_id, task.task_id, "accept" if score >= task.threshold else "reject")
        return PaperDecision(score >= task.threshold, score, trace)

def test_downstream_whole_method_program_keeps_project_typed_io_and_injected_dependencies():
    program = PaperOnlyControlGraph(MeanScore(), "b" * 64)

    assert isinstance(program, ResearchMethodProgram)
    result = program.run(
        task=PaperTask("task-7", 0.5),
        input_value=VectorObservation((0.25, 0.75, 1.0)),
        context=ExecutionContext("run-1", "trace-1", "span-1"),
    )

    assert result == PaperDecision(True, 2.0 / 3.0, ("run-1", "task-7", "accept"))
    assert not hasattr(program, "recall")
    assert not hasattr(program, "task_completed")


@pytest.mark.parametrize("value", ("", "x" * 64, "A" * 64, "a" * 63))
def test_method_program_identity_rejects_noncanonical_configuration_digest(value: str):
    with pytest.raises(ValueError, match="configuration_digest"):
        MethodProgramIdentity(MethodIdentity("m", "1", "abi", "schema", "c" * 64), value)


def test_method_program_identity_separates_configuration_from_implementation_identity():
    implementation = MethodIdentity("m", "1", "abi", "schema", "c" * 64)
    assert MethodProgramIdentity(implementation, None).digest() != MethodProgramIdentity(implementation, "d" * 64).digest()


@pytest.mark.parametrize("value", ("bogus", "g" * 64, "A" * 64, "a" * 63))
def test_method_runtime_identity_rejects_noncanonical_artifact_digest(value: str):
    with pytest.raises(ValueError, match="artifact_digest"):
        MethodRuntimeIdentity("runtime", "1", "abi1", value)


def test_method_runtime_identity_accepts_canonical_artifact_digest():
    identity = MethodRuntimeIdentity("runtime", "1", "abi1", "e" * 64)
    assert identity.artifact_digest == "e" * 64
