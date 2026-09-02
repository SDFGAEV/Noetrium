from __future__ import annotations

from dataclasses import replace
import math

import pytest

from noetrium_platform.research.experimentation.workload.api import WorkloadDecision, WorkloadTaskResult


def _result() -> WorkloadTaskResult:
    return WorkloadTaskResult(
        task_id="task-1",
        family="family",
        success=True,
        utility=1.0,
        steps=1,
        duration_s=0.25,
        lineage_id="lineage-1",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("success", 1),
        ("blocked", 0),
        ("steps", True),
        ("memory_queries", False),
        ("utility", math.nan),
        ("duration_s", math.inf),
        ("duration_s", -0.1),
        ("failure_scope", "unknown"),
    ],
)
def test_workload_task_result_rejects_invalid_typed_state(field, value) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_result(), **{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"blocked": True},
        {"failure_reason": "unexpected_failure"},
        {"success": False},
        {"success": False, "blocked": True},
    ],
)
def test_workload_task_result_rejects_impossible_outcome_combinations(changes) -> None:
    with pytest.raises(ValueError):
        replace(_result(), **changes)


def test_workload_task_result_accepts_explicit_failed_and_blocked_outcomes() -> None:
    failed = replace(_result(), success=False, failure_reason="task_failed")
    blocked = replace(
        _result(), success=False, blocked=True, failure_reason="blocked_dependency"
    )
    assert not failed.success and not failed.blocked
    assert not blocked.success and blocked.blocked

def test_workload_decision_deep_freezes_json_payload() -> None:
    payload = {"nested": {"values": [1, 2]}}
    decision = WorkloadDecision("act", payload, rationale="reason", completion_claim=False)
    payload["nested"]["values"].append(3)
    payload["nested"]["later"] = True
    nested = decision.payload["nested"]
    assert tuple(nested["values"]) == (1, 2)
    assert "later" not in nested
    with pytest.raises(TypeError):
        decision.payload["new"] = 1


def test_workload_decision_rejects_non_json_or_non_finite_payload_state() -> None:
    with pytest.raises(TypeError, match="unsupported object"):
        WorkloadDecision("act", {"bad": object()})
    with pytest.raises(ValueError, match="non-finite"):
        WorkloadDecision("act", {"bad": math.nan})
    with pytest.raises(TypeError, match="rationale"):
        WorkloadDecision("act", {}, rationale=1)
    with pytest.raises(TypeError, match="completion_claim"):
        WorkloadDecision("act", {}, completion_claim=1)


def test_workload_task_result_deep_freezes_record_collections() -> None:
    planner = {"action": {"path": [1, 2]}}
    cycle = {"cycle": {"state": ["a"]}}
    diagnostics = {"trace": {"ok": True}}
    result = replace(
        _result(), planner_actions=(planner,), decision_cycles=(cycle,), diagnostics=diagnostics
    )
    planner["action"]["path"].append(3)
    cycle["cycle"]["state"].append("b")
    diagnostics["trace"]["ok"] = False
    assert tuple(result.planner_actions[0]["action"]["path"]) == (1, 2)
    assert tuple(result.decision_cycles[0]["cycle"]["state"]) == ("a",)
    assert result.diagnostics["trace"]["ok"] is True
    with pytest.raises(TypeError):
        result.diagnostics["new"] = 1


def test_workload_task_result_requires_tuple_record_collections() -> None:
    with pytest.raises(TypeError, match="planner_actions must be a tuple"):
        replace(_result(), planner_actions=[{}])
    with pytest.raises(TypeError, match="decision_cycles must be a tuple"):
        replace(_result(), decision_cycles=[{}])
