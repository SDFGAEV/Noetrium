from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pytest

from research_platform.participant.method.api import (
    MethodIdentity,
    MethodProgramIdentity,
    MethodProgramIdentityMismatch,
    MethodRuntimeIdentity,
    ResearchMethodProgram,
    StatefulResearchMethodProgram,
)
from research_platform.platform.kernel import ComponentIdentity, ExecutionContext
from research_platform.participant.api import (
    MethodProjectDefinition, ParticipantRequirement, method_program_identity_for_requirement,
    method_program_identity_for_runtime_binding, require_method_program_runtime_binding,
)
from research_platform.participant.core.api.checkpoint import (
    ParticipantCheckpoint, ParticipantCheckpointIdentityMismatch,
)
from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity, ParticipantRuntimeBinding, ParticipantSessionRuntimeIdentity,
)


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


class StatefulPaperControlGraph(PaperOnlyControlGraph):
    def __init__(self, scorer: ScorePort, configuration_digest: str) -> None:
        super().__init__(scorer, configuration_digest)
        self.counter = 0

    def checkpoint_state(self) -> bytes:
        return str(self.counter).encode('ascii')

    def restore_state(self, payload: bytes) -> None:
        self.counter = int(bytes(payload).decode('ascii'))

    def run(self, *, task: PaperTask, input_value: VectorObservation, context: ExecutionContext) -> PaperDecision:
        self.counter += 1
        return super().run(task=task, input_value=input_value, context=context)


def _participant_binding(configuration_digest: str = 'b' * 64) -> ParticipantRuntimeBinding:
    return ParticipantRuntimeBinding(
        'method',
        ParticipantImplementationIdentity('method', 'paper-only-control', '1', 'abi1', 'schema1', 'a' * 64),
        ParticipantSessionRuntimeIdentity('method-runtime', '1', 'abi1', 'e' * 64),
        configuration_digest,
    )

def _component(binding: ParticipantRuntimeBinding) -> ComponentIdentity:
    return ComponentIdentity('participant.method', binding.digest(), '1', 'schema1', binding.runtime.digest())


def test_stateful_whole_method_reuses_participant_checkpoint_envelope_without_duplicate_identity():
    program = StatefulPaperControlGraph(MeanScore(), 'b' * 64)
    assert isinstance(program, StatefulResearchMethodProgram)
    program.counter = 7
    binding = _participant_binding()
    component = _component(binding)
    checkpoint = ParticipantCheckpoint.capture(binding=binding, component=component, session_id='session-1', opaque_payload=program.checkpoint_state())
    program.counter = 0
    checkpoint.verify(binding=binding, component=component, session_id='session-1')
    program.restore_state(checkpoint.opaque_payload)
    assert program.counter == 7

def test_stateful_whole_method_restore_rejects_incompatible_platform_binding_before_state_mutation():
    program = StatefulPaperControlGraph(MeanScore(), 'b' * 64)
    program.counter = 3
    binding = _participant_binding()
    checkpoint = ParticipantCheckpoint.capture(binding=binding, component=_component(binding), session_id='session-1', opaque_payload=program.checkpoint_state())
    wrong = _participant_binding('c' * 64)
    with pytest.raises(ParticipantCheckpointIdentityMismatch):
        checkpoint.verify(binding=wrong, component=_component(wrong), session_id='session-1')
    assert program.counter == 3


def test_method_program_identity_projects_canonically_through_requirement_and_runtime_binding():
    program = PaperOnlyControlGraph(MeanScore(), 'b' * 64)
    definition = MethodProjectDefinition('method', program.program_identity.implementation, 'b' * 64)
    requirement = definition.requirement()
    binding = ParticipantRuntimeBinding(requirement.role, requirement.implementation, ParticipantSessionRuntimeIdentity('method-runtime', '1', 'abi1', 'e' * 64), requirement.configuration_digest)
    assert method_program_identity_for_requirement(requirement) == program.program_identity
    assert method_program_identity_for_runtime_binding(binding) == program.program_identity
    require_method_program_runtime_binding(program.program_identity, binding)

def test_method_program_identity_mismatch_fails_before_downstream_program_execution():
    program = PaperOnlyControlGraph(MeanScore(), 'b' * 64)
    binding = _participant_binding('c' * 64)
    with pytest.raises(MethodProgramIdentityMismatch, match='does not match'):
        require_method_program_runtime_binding(program.program_identity, binding)


def test_method_program_projection_rejects_non_method_participant_requirement():
    requirement = ParticipantRequirement(
        'agent', ParticipantImplementationIdentity('agent', 'not-a-method', '1', 'abi1', 'schema1', 'a' * 64), None
    )
    with pytest.raises(MethodProgramIdentityMismatch, match='not method'):
        method_program_identity_for_requirement(requirement)
