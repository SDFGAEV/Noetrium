from pathlib import Path
import sqlite3

import pytest

from research_platform.execution.command.api import CommandId
from research_platform.execution.operation.api import (
    EffectId, OperationEffectCertainty, OperationEffectProfile, OperationId, OperationState,
)
from research_platform.execution.operation.providers import SQLiteOperationStore
from research_platform.execution.operation.runtime import OperationOwner
from research_platform.execution.workflow.api import (
    WorkflowGraph, WorkflowOperationBinding, WorkflowProgress, WorkflowProgressConflict,
    WorkflowProgressCorruption, WorkflowRunId, WorkflowStep,
)
from research_platform.execution.workflow.providers import SQLiteWorkflowProgressStore
from research_platform.execution.workflow.runtime import WorkflowProgressOwner
from research_platform.platform.kernel.operation import EffectCertainty, EffectClass, EffectReceipt
from research_platform.reliability.effect.api import EffectReconciliationDisposition, EffectReconciliationProof

DIGEST = "d" * 64

def _graph():
    return WorkflowGraph((
        WorkflowStep("prepare", "prepare"),
        WorkflowStep("effect", "effect", ("prepare",)),
    ))

def _owners(tmp_path: Path, name: str = "workflow"):
    operations = OperationOwner(SQLiteOperationStore(tmp_path / f"{name}-operations.sqlite3"))
    workflow = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / f"{name}.sqlite3"), operations)
    return workflow, operations

def _submit(operations: OperationOwner, operation_id: OperationId, *, effectful: bool = False):
    kwargs = {}
    if effectful:
        kwargs = {
            "effect_profile": OperationEffectProfile.RECONCILABLE,
            "effect_id": EffectId(f"effect:{operation_id.value}"),
            "effect_request_id": f"request:{operation_id.value}",
            "effect_request_digest": DIGEST,
        }
    snapshot, _ = operations.submit(
        CommandId(f"command:{operation_id.value}"), operation_id=operation_id, now_unix=10.0, **kwargs
    )
    return snapshot

def _claim(workflow, operations, run_id, graph, step_id, operation_id, *, effectful=False):
    snapshot = _submit(operations, operation_id, effectful=effectful)
    workflow.claim(run_id, graph, step_id, operation_id)
    return snapshot

def _interrupt_effectful(workflow, operations, run_id, operation_id):
    operations.admit(operation_id, now_unix=11.0)
    operations.begin_execution(operation_id)
    workflow.recover_interrupted(run_id)
    recovered = operations.recover_interrupted(operation_id)
    assert recovered.state is OperationState.UNKNOWN_EFFECT

def _proof(operation, disposition, certainty, *, request_id=None, effect_id=None, digest=None, verification=False):
    effect = None if certainty is None else EffectReceipt(
        effect_id or operation.effect_id.value, digest or operation.effect_request_digest,
        EffectClass.RECONCILABLE, certainty, verification_required=verification,
    )
    return EffectReconciliationProof(
        request_id or operation.effect_request_id, disposition, effect,
    )

def test_workflow_resume_effect_free_requires_explicit_safe_retry(tmp_path: Path):
    owner, operations = _owners(tmp_path, "resume")
    run_id = WorkflowRunId("wf:1")
    owner.start(run_id, _graph())
    operation_id = OperationId("op:prepare")
    _claim(owner, operations, run_id, _graph(), "prepare", operation_id)
    recovered = owner.recover_interrupted(run_id)
    assert recovered.uncertain[0].operation_id == operation_id
    assert owner.ready_steps(run_id, _graph()) == ()
    reconciled = owner.retry_interrupted_effect_free(run_id, "prepare", operation_id)
    assert not reconciled.uncertain
    assert owner.ready_steps(run_id, _graph()) == ("prepare",)

def test_applied_reconciliation_completes_operation_and_workflow(tmp_path: Path):
    owner, operations = _owners(tmp_path, "applied")
    run_id = WorkflowRunId("wf:applied")
    operation_id = OperationId("op:applied")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    progress = owner.reconcile(
        run_id, "prepare", operation_id,
        _proof(operation, EffectReconciliationDisposition.APPLIED, EffectCertainty.EFFECT_CONFIRMED),
    )
    assert progress.completed[0].operation_id == operation_id
    assert operations.require(operation_id).state is OperationState.COMPLETED
    assert operations.require(operation_id).effect_certainty is OperationEffectCertainty.EXECUTED
    assert owner.ready_steps(run_id, _graph()) == ("effect",)

def test_unknown_reconciliation_preserves_uncertainty_without_version_advance(tmp_path: Path):
    owner, operations = _owners(tmp_path, "unknown")
    run_id = WorkflowRunId("wf:unknown")
    operation_id = OperationId("op:unknown")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    before = owner.require(run_id)
    after = owner.reconcile(
        run_id, "prepare", operation_id,
        _proof(operation, EffectReconciliationDisposition.UNKNOWN, None),
    )
    assert after == before
    assert after.version == before.version
    assert operations.require(operation_id).state is OperationState.UNKNOWN_EFFECT

def test_not_applied_requires_no_effect_and_releases_retry(tmp_path: Path):
    owner, operations = _owners(tmp_path, "not-applied")
    run_id = WorkflowRunId("wf:not-applied")
    operation_id = OperationId("op:not-applied")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    with pytest.raises(ValueError, match="disposition/certainty"):
        owner.reconcile(
            run_id, "prepare", operation_id,
            _proof(operation, EffectReconciliationDisposition.NOT_APPLIED, EffectCertainty.EFFECT_CONFIRMED),
        )
    assert owner.require(run_id).uncertain
    progress = owner.reconcile(
        run_id, "prepare", operation_id,
        _proof(operation, EffectReconciliationDisposition.NOT_APPLIED, EffectCertainty.NO_EFFECT),
    )
    assert not progress.uncertain
    assert operations.require(operation_id).effect_certainty is OperationEffectCertainty.NOT_EXECUTED
    assert owner.ready_steps(run_id, _graph()) == ("prepare",)

def test_rejected_reconciliation_fails_operation_and_workflow(tmp_path: Path):
    owner, operations = _owners(tmp_path, "rejected")
    run_id = WorkflowRunId("wf:rejected")
    operation_id = OperationId("op:rejected")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    progress = owner.reconcile(
        run_id, "prepare", operation_id,
        _proof(operation, EffectReconciliationDisposition.REJECTED, EffectCertainty.EFFECT_REJECTED),
    )
    assert progress.failed is not None and progress.failed.operation_id == operation_id
    assert operations.require(operation_id).state is OperationState.FAILED

@pytest.mark.parametrize("mutation", ["request", "effect", "digest", "verification"])
def test_reconciliation_identity_mismatch_fails_closed(tmp_path: Path, mutation: str):
    owner, operations = _owners(tmp_path, f"mismatch-{mutation}")
    run_id = WorkflowRunId(f"wf:mismatch:{mutation}")
    operation_id = OperationId(f"op:mismatch:{mutation}")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    kwargs = {
        "request_id": "wrong-request" if mutation == "request" else None,
        "effect_id": "wrong-effect" if mutation == "effect" else None,
        "digest": "e" * 64 if mutation == "digest" else None,
        "verification": mutation == "verification",
    }
    with pytest.raises(ValueError):
        owner.reconcile(
            run_id, "prepare", operation_id,
            _proof(operation, EffectReconciliationDisposition.APPLIED, EffectCertainty.EFFECT_CONFIRMED, **kwargs),
        )
    assert owner.require(run_id).uncertain
    assert operations.require(operation_id).state is OperationState.UNKNOWN_EFFECT

def test_workflow_reconciliation_rejects_caller_selected_disposition(tmp_path: Path):
    owner, operations = _owners(tmp_path, "forged")
    run_id = WorkflowRunId("wf:forged")
    operation_id = OperationId("op:forged")
    owner.start(run_id, _graph())
    _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    _interrupt_effectful(owner, operations, run_id, operation_id)
    with pytest.raises(TypeError, match="EffectReconciliationProof"):
        owner.reconcile(
            run_id, "prepare", operation_id, EffectReconciliationDisposition.APPLIED  # type: ignore[arg-type]
        )

def test_durable_binding_persists_exact_effect_request_identity(tmp_path: Path):
    owner, operations = _owners(tmp_path, "identity")
    run_id = WorkflowRunId("wf:identity")
    operation_id = OperationId("op:identity")
    owner.start(run_id, _graph())
    operation = _claim(owner, operations, run_id, _graph(), "prepare", operation_id, effectful=True)
    restarted = WorkflowProgressOwner(
        SQLiteWorkflowProgressStore(tmp_path / "identity.sqlite3"),
        OperationOwner(SQLiteOperationStore(tmp_path / "identity-operations.sqlite3")),
    )
    binding = restarted.require(run_id).running[0]
    assert binding.effect_id == operation.effect_id
    assert binding.effect_request_id == operation.effect_request_id
    assert binding.effect_request_digest == operation.effect_request_digest

def test_workflow_cancel_returns_bound_operation_ids(tmp_path: Path):
    owner, operations = _owners(tmp_path, "cancel")
    run_id = WorkflowRunId("wf:cancel")
    graph = WorkflowGraph((WorkflowStep("a", "a"), WorkflowStep("b", "b")))
    owner.start(run_id, graph)
    _claim(owner, operations, run_id, graph, "a", OperationId("op:a"))
    _claim(owner, operations, run_id, graph, "b", OperationId("op:b"))
    progress, operation_ids = owner.request_cancel(run_id, "user cancelled")
    assert progress.cancellation_requested
    assert {item.value for item in operation_ids} == {"op:a", "op:b"}
    assert owner.ready_steps(run_id, graph) == ()

def test_workflow_store_rejects_corrupt_json_shape(tmp_path: Path):
    owner, _ = _owners(tmp_path, "corrupt")
    run_id = WorkflowRunId("wf:corrupt")
    owner.start(run_id, _graph())
    path = tmp_path / "corrupt.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE workflow_progress SET completed_json=? WHERE workflow_run_id=?", ('"prepare"', run_id.value))
    with pytest.raises(WorkflowProgressCorruption):
        SQLiteWorkflowProgressStore(path).load(run_id)

def test_workflow_store_rejects_legacy_two_field_binding_shape(tmp_path: Path):
    owner, _ = _owners(tmp_path, "legacy-binding")
    run_id = WorkflowRunId("wf:legacy-binding")
    owner.start(run_id, _graph())
    path = tmp_path / "legacy-binding.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE workflow_progress SET completed_json=? WHERE workflow_run_id=?",
            ('[["prepare","op:legacy"]]', run_id.value),
        )
    with pytest.raises(WorkflowProgressCorruption, match="effect_id"):
        SQLiteWorkflowProgressStore(path).load(run_id)

def test_stale_completion_cannot_complete_retried_step(tmp_path: Path):
    owner, operations = _owners(tmp_path, "stale-complete")
    run_id = WorkflowRunId("wf:stale-complete")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    old_operation, new_operation = OperationId("op:old"), OperationId("op:new")
    owner.start(run_id, graph)
    old = _claim(owner, operations, run_id, graph, "effect", old_operation, effectful=True)
    _interrupt_effectful(owner, operations, run_id, old_operation)
    owner.reconcile(
        run_id, "effect", old_operation,
        _proof(old, EffectReconciliationDisposition.NOT_APPLIED, EffectCertainty.NO_EFFECT),
    )
    _claim(owner, operations, run_id, graph, "effect", new_operation)
    with pytest.raises(RuntimeError, match="stale workflow operation completion rejected"):
        owner.complete(run_id, "effect", old_operation)
    operations.admit(new_operation, now_unix=11.0)
    operations.begin_execution(new_operation)
    operations.complete(new_operation)
    completed = owner.complete(run_id, "effect", new_operation)
    assert completed.completed[0].operation_id == new_operation

def test_stale_failure_cannot_fail_retried_step(tmp_path: Path):
    owner, operations = _owners(tmp_path, "stale-fail")
    run_id = WorkflowRunId("wf:stale-fail")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    old_operation, new_operation = OperationId("op:old"), OperationId("op:new")
    owner.start(run_id, graph)
    _claim(owner, operations, run_id, graph, "effect", old_operation)
    owner.recover_interrupted(run_id)
    owner.retry_interrupted_effect_free(run_id, "effect", old_operation)
    _claim(owner, operations, run_id, graph, "effect", new_operation)
    with pytest.raises(RuntimeError, match="stale workflow operation completion rejected"):
        owner.fail(run_id, "effect", old_operation)
    failed = owner.fail(run_id, "effect", new_operation)
    assert failed.failed is not None and failed.failed.operation_id == new_operation

def test_workflow_store_rejects_incompatible_existing_schema(tmp_path: Path):
    path = tmp_path / "workflow-old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE workflow_progress (workflow_run_id TEXT PRIMARY KEY)")
    with pytest.raises(WorkflowProgressCorruption):
        SQLiteWorkflowProgressStore(path)

def test_workflow_start_replay_preserves_existing_progress(tmp_path: Path):
    owner, operations = _owners(tmp_path, "start-replay")
    run_id = WorkflowRunId("wf:start-replay")
    graph = _graph()
    owner.start(run_id, graph)
    operation_id = OperationId("op:prepare")
    _claim(owner, operations, run_id, graph, "prepare", operation_id)
    claimed = owner.require(run_id)
    assert owner.start(run_id, graph) == claimed

def test_workflow_start_rejects_graph_drift_for_existing_run(tmp_path: Path):
    owner, _ = _owners(tmp_path, "start-drift")
    run_id = WorkflowRunId("wf:start-drift")
    owner.start(run_id, _graph())
    with pytest.raises(ValueError, match="durable workflow identity"):
        owner.start(run_id, WorkflowGraph((WorkflowStep("other", "other"),)))

def test_workflow_first_failure_wins_and_replay_is_idempotent(tmp_path: Path):
    owner, operations = _owners(tmp_path, "first-failure")
    run_id = WorkflowRunId("wf:first-failure")
    graph = WorkflowGraph((WorkflowStep("a", "a"), WorkflowStep("b", "b")))
    op_a, op_b = OperationId("op:a"), OperationId("op:b")
    owner.start(run_id, graph)
    _claim(owner, operations, run_id, graph, "a", op_a)
    _claim(owner, operations, run_id, graph, "b", op_b)
    first = owner.fail(run_id, "a", op_a)
    assert owner.fail(run_id, "a", op_a) == first
    with pytest.raises(RuntimeError, match="already failed"):
        owner.fail(run_id, "b", op_b)
    assert owner.require(run_id).failed == first.failed

def test_workflow_store_rejects_nonempty_initial_progress(tmp_path: Path):
    store = SQLiteWorkflowProgressStore(tmp_path / "workflow-initial.sqlite3")
    invalid = WorkflowProgress(
        WorkflowRunId("wf:invalid-initial"), "a" * 64, 1,
        running=(WorkflowOperationBinding("ghost", OperationId("op:ghost")),),
    )
    with pytest.raises(WorkflowProgressConflict):
        store.create(invalid)

def test_workflow_store_cas_rejects_graph_drift_and_version_skip(tmp_path: Path):
    owner, _ = _owners(tmp_path, "cas")
    store = owner._store
    run_id = WorkflowRunId("wf:cas")
    current = owner.start(run_id, _graph())
    for candidate in (WorkflowProgress(run_id, "b" * 64, 1), WorkflowProgress(run_id, current.graph_digest, 2)):
        with pytest.raises(WorkflowProgressConflict):
            store.compare_and_swap(0, candidate)
