from __future__ import annotations

import pytest

from noetrium_platform.research.experimentation.experiment.runtime import ExperimentWorkflowSurfaceRegistry


def test_unknown_workflow_surface_fails_without_constructing_scientific_operations():
    registry = ExperimentWorkflowSurfaceRegistry(())
    with pytest.raises(LookupError):
        registry.bind("future.unknown.surface", object())


def test_builtin_workflows_declare_distinct_narrow_surfaces():
    from noetrium_platform.research.execution.workflow.implementations.agent_turn.agent_turn_workflow import AgentTurnTrialProtocol
    from noetrium_platform.research.execution.workflow.implementations.context_action.context_action_workflow import ContextActionTrialProtocol

    assert AgentTurnTrialProtocol.surface_id == "agent_turn.operations.v1"
    assert ContextActionTrialProtocol.surface_id == "context_action.operations.v1"
    assert AgentTurnTrialProtocol.surface_id != ContextActionTrialProtocol.surface_id
