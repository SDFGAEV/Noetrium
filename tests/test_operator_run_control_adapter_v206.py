from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import importlib.util
from types import SimpleNamespace

import pytest

from noetrium_platform.product.operator.api import (
    ResearchAction,
    ResearchOperationFailure,
    ResearchRequest,
)
import noetrium_platform.product.operator.runtime.run_control_application as adapter
from noetrium_platform.product.operator.runtime.run_control_application import (
    RunControlResearchBinding,
    bind_run_control_application,
)


class _Action(StrEnum):
    RUN = "run"
    INSPECT = "inspect"
    STOP = "stop"
    RESUME = "resume"
    RECONCILE = "reconcile"
    EVIDENCE = "evidence"


class _Phase(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    RECOVERY_REQUIRED = "recovery_required"
    FAILED = "failed"


class _RecordKind(StrEnum):
    TERMINAL = "terminal"


class _OutcomeValue(StrEnum):
    IN_PROGRESS = "in_progress"
    STOPPED = "stopped"
    RECOVERY_REQUIRED = "recovery_required"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"
    NOT_OBSERVED = "not_observed"
    NOT_FINALIZED = "not_finalized"


@dataclass(frozen=True)
class _Outcomes:
    execution: _OutcomeValue
    task: _OutcomeValue
    evidence: _OutcomeValue
    scientific: _OutcomeValue


@dataclass(frozen=True)
class _Target:
    run_id: str
    run_manifest_digest: str
    expected_generation: int | None = None


@dataclass(frozen=True)
class _Request:
    action: _Action
    target: _Target
    restore_checkpoint_id: str | None = None
    restore_cycle_identity: object | None = None


@dataclass(frozen=True)
class _Event:
    record_sequence: int
    record_kind: _RecordKind
    control_generation: int
    action: _Action
    phase: _Phase
    operation_id: str
    event_digest: str


@dataclass(frozen=True)
class _Receipt:
    action: _Action
    run_id: str
    run_identity_digest: str
    run_manifest_digest: str
    phase: _Phase
    control_generation: int
    latest_checkpoint_id: str | None
    checkpoint_manifest_digest: str | None
    evidence_bundle_receipt: object | None
    outcomes: _Outcomes
    control_event_receipt: _Event


class _ControlError(RuntimeError):
    pass


class _ActionFailure(_ControlError):
    def __init__(self, receipt: _Receipt) -> None:
        self.receipt = receipt
        super().__init__("action failed")


def _contracts():
    return SimpleNamespace(
        RunControlAction=_Action,
        RunControlTarget=_Target,
        RunControlRequest=_Request,
        RunControlReceipt=_Receipt,
        RunControlActionFailure=_ActionFailure,
        RunControlError=_ControlError,
    )


def _receipt(request: _Request, *, phase: _Phase | None = None) -> _Receipt:
    resolved = phase or (_Phase.STOPPED if request.action is _Action.STOP else _Phase.RUNNING)
    generation = request.target.expected_generation or 0
    event = _Event(1, _RecordKind.TERMINAL, generation, request.action, resolved, "c" * 64, "d" * 64)
    execution = {
        _Phase.RUNNING: _OutcomeValue.IN_PROGRESS,
        _Phase.STOPPED: _OutcomeValue.STOPPED,
        _Phase.RECOVERY_REQUIRED: _OutcomeValue.RECOVERY_REQUIRED,
        _Phase.FAILED: _OutcomeValue.FAILED,
    }[resolved]
    evidence = _OutcomeValue.NOT_FINALIZED if request.action is _Action.EVIDENCE else _OutcomeValue.NOT_OBSERVED
    outcomes = _Outcomes(execution, _OutcomeValue.NOT_EVALUATED, evidence, _OutcomeValue.NOT_EVALUATED)
    return _Receipt(
        request.action,
        request.target.run_id,
        "b" * 64,
        request.target.run_manifest_digest,
        resolved,
        generation,
        None,
        None,
        None,
        outcomes,
        event,
    )


class _Control:
    def __init__(self, *, phase: _Phase | None = None, fail: bool = False) -> None:
        self.phase = phase
        self.fail = fail
        self.requests: list[_Request] = []

    def execute(self, request: _Request) -> _Receipt:
        self.requests.append(request)
        receipt = _receipt(request, phase=self.phase)
        if self.fail:
            raise _ActionFailure(receipt)
        return receipt


def _application(monkeypatch, control: _Control | None = None):
    monkeypatch.setattr(adapter, "_load_run_control_contracts", _contracts)
    control = control or _Control()
    return bind_run_control_application(
        control,
        run_id="run-1",
        run_manifest_digest="a" * 64,
    ), control


def _cycle_payload() -> dict[str, str]:
    return {
        "run_id": "run-1",
        "decision_cycle_id": "cycle-1",
        "session_id": "session-1",
        "task_id": "task-1",
        "trace_id": "trace-1",
    }


@pytest.mark.parametrize(
    ("action", "payload", "generation"),
    [
        (ResearchAction.RUN, {"expected_generation": 0}, 0),
        (ResearchAction.INSPECT, None, None),
        (ResearchAction.STOP, {"expected_generation": 1}, 1),
        (ResearchAction.RECONCILE, {"expected_generation": 2}, 2),
        (ResearchAction.EVIDENCE, {"expected_generation": 2}, 2),
    ],
)
def test_adapter_translates_research_actions_into_typed_run_control(
    monkeypatch, action, payload, generation
):
    application, control = _application(monkeypatch)
    result = application.execute(ResearchRequest(action, "run-1", payload))
    (translated,) = control.requests
    assert translated.action.value == action.value
    assert translated.target.run_id == "run-1"
    assert translated.target.run_manifest_digest == "a" * 64
    assert translated.target.expected_generation == generation
    assert result.action is action
    assert result.target == "run-1"
    assert result.payload["run_manifest_digest"] == "a" * 64
    assert result.payload["control_event"]["action"] == action.value


def test_resume_requires_and_preserves_exact_restore_identity(monkeypatch):
    application, control = _application(monkeypatch)
    result = application.execute(ResearchRequest(
        ResearchAction.RESUME,
        "run-1",
        {
            "expected_generation": 4,
            "restore_checkpoint_id": "checkpoint-4",
            "restore_cycle_identity": _cycle_payload(),
        },
    ))
    (translated,) = control.requests
    assert translated.target.expected_generation == 4
    assert translated.restore_checkpoint_id == "checkpoint-4"
    assert translated.restore_cycle_identity.run_id == "run-1"
    assert translated.restore_cycle_identity.decision_cycle_id == "cycle-1"
    assert result.state == "running"


@pytest.mark.parametrize(
    "research_request",
    [
        ResearchRequest(ResearchAction.RUN, "run-1", None),
        ResearchRequest(ResearchAction.RUN, "run-1", {"expected_generation": True}),
        ResearchRequest(ResearchAction.STOP, "run-1", {"expected_generation": 1, "extra": 1}),
        ResearchRequest(ResearchAction.RESUME, "run-1", {"expected_generation": 1}),
        ResearchRequest(ResearchAction.INSPECT, "run-1", {"unexpected": 1}),
    ],
)
def test_adapter_rejects_unfenced_or_non_exact_payloads(monkeypatch, research_request):
    application, _control = _application(monkeypatch)
    with pytest.raises((TypeError, ValueError)):
        application.execute(research_request)


def test_adapter_rejects_target_identity_drift(monkeypatch):
    application, _control = _application(monkeypatch)
    with pytest.raises(ValueError, match="bound run identity"):
        application.execute(ResearchRequest(ResearchAction.INSPECT, "other-run"))


def test_state_change_recovery_required_surfaces_authoritative_failure(monkeypatch):
    application, _control = _application(
        monkeypatch,
        _Control(phase=_Phase.RECOVERY_REQUIRED),
    )
    with pytest.raises(ResearchOperationFailure) as captured:
        application.execute(ResearchRequest(
            ResearchAction.RECONCILE,
            "run-1",
            {"expected_generation": 3},
        ))
    assert captured.value.result.state == "recovery_required"
    assert captured.value.result.payload["control_generation"] == 3


def test_run_control_action_failure_preserves_authoritative_receipt(monkeypatch):
    application, _control = _application(
        monkeypatch,
        _Control(phase=_Phase.RECOVERY_REQUIRED, fail=True),
    )
    with pytest.raises(ResearchOperationFailure) as captured:
        application.execute(ResearchRequest(
            ResearchAction.RUN,
            "run-1",
            {"expected_generation": 0},
        ))
    assert captured.value.result.action is ResearchAction.RUN
    assert captured.value.result.state == "recovery_required"


def test_read_only_inspect_can_report_failed_state_without_manufacturing_failure(monkeypatch):
    application, _control = _application(monkeypatch, _Control(phase=_Phase.FAILED))
    result = application.execute(ResearchRequest(ResearchAction.INSPECT, "run-1"))
    assert result.state == "failed"


def test_adapter_rejects_non_typed_receipt(monkeypatch):
    class _BadControl:
        def execute(self, request):
            return object()

    application, _control = _application(monkeypatch, _BadControl())
    with pytest.raises(TypeError, match="non-RunControlReceipt"):
        application.execute(ResearchRequest(ResearchAction.INSPECT, "run-1"))


def test_adapter_consumes_real_role03_run_control_contract_when_available():
    try:
        spec = importlib.util.find_spec("noetrium_platform.research.experimentation.run.control.api")
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        pytest.skip("ROLE03 run-control dependency is not present in this branch cut")
    from noetrium_platform.research.experimentation.run.control.api import (
        RunControlAction,
        RunControlEventReceipt,
        RunControlPhase,
        RunControlReceipt,
        RunEvidenceValidity,
        RunExecutionOutcome,
        RunOutcomeProjection,
        RunScientificValidity,
        RunTaskOutcome,
    )
    from noetrium_platform.research.experimentation.run.control.api.contracts import RunControlRecordKind

    class _RealControl:
        def execute(self, request):
            event = RunControlEventReceipt(
                "run-1", 1, RunControlRecordKind.TERMINAL, 0,
                RunControlAction.INSPECT, RunControlPhase.STOPPED,
                "c" * 64, "d" * 64,
            )
            outcomes = RunOutcomeProjection(
                RunExecutionOutcome.STOPPED,
                RunTaskOutcome.NOT_EVALUATED,
                RunEvidenceValidity.NOT_OBSERVED,
                RunScientificValidity.NOT_EVALUATED,
            )
            return RunControlReceipt(
                RunControlAction.INSPECT, "run-1", "b" * 64, "a" * 64,
                RunControlPhase.STOPPED, 0, None, None, None, outcomes, event,
            )

    application = bind_run_control_application(
        _RealControl(),
        run_id="run-1",
        run_manifest_digest="a" * 64,
    )
    result = application.execute(ResearchRequest(ResearchAction.INSPECT, "run-1"))
    assert result.state == "stopped"
    assert result.payload["run_identity_digest"] == "b" * 64
    assert result.payload["control_event"]["record_kind"] == "terminal"
    assert result.payload["outcomes"]["execution"] == RunExecutionOutcome.STOPPED.value
    assert result.payload["outcomes"]["task"] == RunTaskOutcome.NOT_EVALUATED.value
    assert result.payload["outcomes"]["evidence"] == RunEvidenceValidity.NOT_OBSERVED.value
    assert result.payload["outcomes"]["scientific"] == RunScientificValidity.NOT_EVALUATED.value

def test_adapter_rejects_control_event_action_drift(monkeypatch):
    class _DriftControl:
        def execute(self, request):
            receipt = _receipt(request)
            event = _Event(
                receipt.control_event_receipt.record_sequence,
                receipt.control_event_receipt.record_kind,
                receipt.control_event_receipt.control_generation,
                _Action.STOP,
                receipt.control_event_receipt.phase,
                receipt.control_event_receipt.operation_id,
                receipt.control_event_receipt.event_digest,
            )
            return _Receipt(
                receipt.action, receipt.run_id, receipt.run_identity_digest,
                receipt.run_manifest_digest, receipt.phase, receipt.control_generation,
                receipt.latest_checkpoint_id, receipt.checkpoint_manifest_digest,
                receipt.evidence_bundle_receipt, receipt.outcomes, event,
            )

    application, _control = _application(monkeypatch, _DriftControl())
    with pytest.raises(ValueError, match="event action drifted"):
        application.execute(ResearchRequest(ResearchAction.INSPECT, "run-1"))


def test_adapter_rejects_foreign_evidence_identity(monkeypatch):
    class _EvidenceControl:
        def execute(self, request):
            receipt = _receipt(request)
            evidence = SimpleNamespace(run_id="other-run", run_manifest_digest="a" * 64)
            return _Receipt(
                receipt.action, receipt.run_id, receipt.run_identity_digest,
                receipt.run_manifest_digest, receipt.phase, receipt.control_generation,
                receipt.latest_checkpoint_id, receipt.checkpoint_manifest_digest, evidence,
                receipt.outcomes, receipt.control_event_receipt,
            )

    application, _control = _application(monkeypatch, _EvidenceControl())
    with pytest.raises(ValueError, match="evidence identity drifted"):
        application.execute(ResearchRequest(ResearchAction.EVIDENCE, "run-1"))
