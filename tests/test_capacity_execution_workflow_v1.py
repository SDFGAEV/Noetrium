from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from noetrium_platform.research.execution.command.api import CommandId
from noetrium_platform.research.execution.operation.api import OperationId
from noetrium_platform.research.execution.operation.providers import SQLiteOperationStore
from noetrium_platform.research.execution.operation.runtime import OperationOwner
from noetrium_platform.research.execution.workflow.api import (
    WorkflowGraph, WorkflowProgressConflict, WorkflowRunId, WorkflowStep,
)
from noetrium_platform.research.execution.workflow.providers import SQLiteWorkflowProgressStore
from noetrium_platform.research.execution.workflow.runtime import WorkflowProgressOwner

def _operation_owner(path: Path) -> OperationOwner:
    return OperationOwner(SQLiteOperationStore(path))

def _workflow_owner(workflow_path: Path, operation_path: Path) -> WorkflowProgressOwner:
    return WorkflowProgressOwner(SQLiteWorkflowProgressStore(workflow_path), _operation_owner(operation_path))

def test_concurrent_claim_of_same_step_has_one_winner(tmp_path: Path):
    workflow_path = tmp_path / "workflow.sqlite3"
    operation_path = tmp_path / "operations.sqlite3"
    run_id = WorkflowRunId("wf:race")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    _workflow_owner(workflow_path, operation_path).start(run_id, graph)
    operations = _operation_owner(operation_path)
    for index in range(16):
        operations.submit(
            CommandId(f"cmd:{index}"), operation_id=OperationId(f"op:{index}"), now_unix=10.0
        )

    def claim(index: int) -> bool:
        owner = _workflow_owner(workflow_path, operation_path)
        try:
            owner.claim(run_id, graph, "effect", OperationId(f"op:{index}"))
            return True
        except (RuntimeError, WorkflowProgressConflict):
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = tuple(pool.map(claim, range(16)))
    assert sum(outcomes) == 1
    final = _workflow_owner(workflow_path, operation_path).require(run_id)
    assert len(final.running) == 1

def test_claim_reads_durable_progress_once_before_cas(tmp_path: Path):
    workflow_path = tmp_path / "workflow-loads.sqlite3"
    operation_path = tmp_path / "operations-loads.sqlite3"
    store = SQLiteWorkflowProgressStore(workflow_path)
    operations = _operation_owner(operation_path)
    operation_id = OperationId("op:single-load")
    operations.submit(CommandId("cmd:single-load"), operation_id=operation_id, now_unix=10.0)
    owner = WorkflowProgressOwner(store, operations)
    run_id = WorkflowRunId("wf:single-load")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    owner.start(run_id, graph)
    original_load = store.load
    calls = 0

    def counted_load(workflow_run_id):
        nonlocal calls
        calls += 1
        return original_load(workflow_run_id)

    store.load = counted_load  # type: ignore[method-assign]
    owner.claim(run_id, graph, "effect", operation_id)
    assert calls == 1

def test_concurrent_workflow_start_is_replay_safe(tmp_path: Path):
    workflow_path = tmp_path / "workflow-start-race.sqlite3"
    operation_path = tmp_path / "operations-start-race.sqlite3"
    run_id = WorkflowRunId("wf:start-race")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))

    def start(_: int):
        return _workflow_owner(workflow_path, operation_path).start(run_id, graph)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = tuple(pool.map(start, range(16)))
    assert len(outcomes) == 16
    assert all(item.workflow_run_id == run_id for item in outcomes)
    assert len({item.graph_digest for item in outcomes}) == 1
    assert all(item.version == 0 for item in outcomes)
    final = _workflow_owner(workflow_path, operation_path).require(run_id)
    assert final == outcomes[0]
