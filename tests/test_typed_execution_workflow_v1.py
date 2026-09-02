from noetrium_platform.research.execution.workflow.api import (
    WorkflowGraph,
    WorkflowGraphError,
    WorkflowProgress,
    WorkflowRunId,
    WorkflowStep,
)
from noetrium_platform.research.execution.workflow.runtime import workflow_graph_digest


def test_workflow_graph_is_explicit_and_deterministic():
    graph = WorkflowGraph((
        WorkflowStep("prepare", "effect.prepare"),
        WorkflowStep("left", "work.left", ("prepare",)),
        WorkflowStep("right", "work.right", ("prepare",)),
        WorkflowStep("commit", "effect.commit", ("left", "right")),
    ))
    assert graph.topological_order() == ("prepare", "left", "right", "commit")
    assert graph.ready_steps(frozenset({"prepare"})) == ("left", "right")


def test_workflow_graph_rejects_cycle_and_missing_dependency():
    for steps in (
        (WorkflowStep("a", "a", ("b",)), WorkflowStep("b", "b", ("a",))),
        (WorkflowStep("a", "a", ("missing",)),),
    ):
        try:
            WorkflowGraph(steps)
        except WorkflowGraphError:
            pass
        else:
            raise AssertionError("invalid workflow graph must fail before side effects")


def test_workflow_digest_is_semantic_not_declaration_order():
    first = WorkflowGraph((
        WorkflowStep("a", "work.a", required_capabilities=("z", "x")),
        WorkflowStep("b", "work.b", ("a",)),
    ))
    second = WorkflowGraph((
        WorkflowStep("b", "work.b", ("a",)),
        WorkflowStep("a", "work.a", required_capabilities=("x", "z")),
    ))
    assert first.topological_order() == second.topological_order()
    assert workflow_graph_digest(first) == workflow_graph_digest(second)


def test_workflow_identity_fields_do_not_coerce_non_text_values():
    try:
        WorkflowStep(1, "work")  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("workflow step identity must remain typed")

    try:
        WorkflowStep("step", "work", dependencies=(1,))  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("workflow dependency identity must remain typed")


def test_workflow_progress_rejects_permissive_type_coercion():
    run_id = WorkflowRunId("wf:typed")
    digest = "a" * 64
    for version in (False, 1.5):
        try:
            WorkflowProgress(run_id, digest, version)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError("workflow progress version must be a real integer")

    for kwargs in (
        {"graph_digest": 1},
        {"cancellation_requested": 1},
        {"cancellation_requested": True, "cancellation_reason": 42},
    ):
        values = {"workflow_run_id": run_id, "graph_digest": digest, "version": 0, **kwargs}
        try:
            WorkflowProgress(**values)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError("workflow durable fields must not coerce arbitrary objects")
