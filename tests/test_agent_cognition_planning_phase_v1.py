from __future__ import annotations

from research_platform.participant.agent.api import (
    AgentActionSequence,
    AgentActionStep,
    AgentGoal,
    AgentMemoryContext,
    AgentModeDecision,
    AgentModeDisposition,
    AgentObservation,
    AgentSafetyDecision,
    AgentSafetyDisposition,
    AgentSkillDescription,
    AgentSkillSelection,
)
from research_platform.participant.agent.runtime.cognition_context import CognitionContextPhase
from research_platform.participant.agent.runtime.cognition_planning import (
    CognitionPlanningPhase,
    PlanningDisposition,
)
from research_platform.participant.agent.runtime.cognition_reasoning import CognitionReasoningPhase
from research_platform.platform.kernel import ExecutionContext


_CONTEXT = ExecutionContext("run", "trace", "span")
_GOAL = AgentGoal("goal", "do task")
_OBSERVATION = AgentObservation("obs", "world", {"x": 1})


class _Memory:
    def recall(self, goal, observation, context):
        del goal, context
        return AgentMemoryContext("memory", observation.generation)

    def record(self, receipt, context):
        del receipt, context


class _Planner:
    def __init__(self) -> None:
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return AgentSkillSelection("skill.test", {"value": request.step})


class _Skills:
    def describe(self):
        return (AgentSkillDescription("skill.test", "test", "test skill", "{}", True),)

    def expand(self, selection, *, observation, context, sequence_id):
        del observation, context
        step = AgentActionStep(
            f"{sequence_id}:0", "move", dict(selection.arguments), selection.skill_id,
            sequence_id, 0,
        )
        return AgentActionSequence(sequence_id, selection.skill_id, (step,))


class _Completion:
    def is_complete(self, goal, observation, *, planner_finished, last_receipt):
        del goal, observation, planner_finished, last_receipt
        return False


class _Safety:
    def __init__(self, disposition, replacement=None):
        self.disposition = disposition
        self.replacement = replacement

    def review(self, goal, observation, selection, sequence, context):
        del goal, observation, selection, sequence, context
        return AgentSafetyDecision(self.disposition, "decision", "test", self.replacement)


class _Mode:
    def __init__(self, decision):
        self.decision = decision

    def review(self, goal, observation, selection, sequence, context):
        del goal, observation, selection, sequence, context
        return self.decision


def _replacement() -> AgentActionSequence:
    sequence_id = "replacement"
    step = AgentActionStep("replacement:0", "retreat", {}, "skill.test", sequence_id, 0)
    return AgentActionSequence(sequence_id, "skill.test", (step,))


def _phases(*, safety, mode=None):
    skills = _Skills()
    planner = _Planner()
    context = CognitionContextPhase(
        memory=_Memory(), skill_library=None, failure=lambda *args, **kwargs: None,
    )
    planning = CognitionPlanningPhase(
        skills=skills,
        safety=safety,
        completion=_Completion(),
        skill_library=None,
        reactive_modes=mode,
        event=lambda *args, **kwargs: None,
        failure=lambda *args, **kwargs: None,
    )
    reasoning = CognitionReasoningPhase(
        planner=planner,
        available_skills=planning.available_skills,
        failure=lambda *args, **kwargs: None,
    )
    return context, reasoning, planning, planner


def _plan(*, safety, mode=None):
    context, reasoning, planning, planner = _phases(safety=safety, mode=mode)
    snapshot = context.gather(goal=_GOAL, observation=_OBSERVATION, context=_CONTEXT)
    reasoned = reasoning.reason(
        goal=_GOAL,
        observation=_OBSERVATION,
        context_snapshot=snapshot,
        plan_context=_CONTEXT,
        step=0,
        plan_call=0,
        prior_actions=(),
    )
    result = planning.plan(
        selection=reasoned.selection,
        goal=_GOAL,
        observation=_OBSERVATION,
        plan_context=_CONTEXT,
        plan_call=0,
        last_receipt=None,
    )
    return result, snapshot, reasoned, planner


def test_context_and_reasoning_are_distinct_typed_boundaries() -> None:
    result, snapshot, reasoned, planner = _plan(
        safety=_Safety(AgentSafetyDisposition.ALLOW)
    )
    assert snapshot.memory.context_text == "memory"
    assert reasoned.request.memory is snapshot.memory
    assert reasoned.request.available_skills[0].skill_id == "skill.test"
    assert planner.requests == [reasoned.request]
    assert result.selection is reasoned.selection


def test_safety_replan_is_a_typed_planning_outcome() -> None:
    result, _, _, _ = _plan(safety=_Safety(AgentSafetyDisposition.REPLAN))
    assert result.disposition is PlanningDisposition.REPLAN
    assert result.next_plan_call == 1


def test_reactive_mode_abort_is_distinct_from_safety_abort() -> None:
    mode = _Mode(AgentModeDecision("mode.stop", AgentModeDisposition.ABORT, "stop"))
    result, _, _, _ = _plan(safety=_Safety(AgentSafetyDisposition.ALLOW), mode=mode)
    assert result.disposition is PlanningDisposition.MODE_ABORT


def test_preempted_sequence_crosses_phase_boundary_as_typed_sequence() -> None:
    replacement = _replacement()
    result, _, _, _ = _plan(
        safety=_Safety(AgentSafetyDisposition.PREEMPT, replacement)
    )
    assert result.disposition is PlanningDisposition.EXECUTE
    assert result.sequence is replacement
    assert result.sequence.steps[0].action_type == "retreat"
