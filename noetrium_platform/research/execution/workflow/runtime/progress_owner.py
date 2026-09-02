from __future__ import annotations

from dataclasses import replace
import hashlib
import json

from noetrium_platform.research.execution.operation.api import (
    OperationEffectCertainty, OperationEffectProfile, OperationId, OperationRecoveryPort, OperationState,
)
from noetrium_platform.infrastructure.reliability.effect.api import EffectReconciliationDisposition, EffectReconciliationProof
from noetrium_platform.research.execution.workflow.api.graph import WorkflowGraph
from noetrium_platform.research.execution.workflow.api.progress import (
    WorkflowOperationBinding,
    WorkflowProgress,
    WorkflowProgressConflict,
    WorkflowProgressStorePort,
    WorkflowRunId,
)


def workflow_graph_digest(graph: WorkflowGraph) -> str:
    payload = [
        [step.step_id, step.operation_type, sorted(step.dependencies), sorted(step.required_capabilities)]
        for step in sorted(graph.steps, key=lambda item: item.step_id)
    ]
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class WorkflowProgressOwner:
    """Single durable owner for workflow progress and step/operation ancestry."""

    def __init__(self, store: WorkflowProgressStorePort, operations: OperationRecoveryPort) -> None:
        self._store = store
        self._operations = operations

    @property
    def durability(self) -> str:
        return self._store.durability

    def start(self, workflow_run_id: WorkflowRunId, graph: WorkflowGraph) -> WorkflowProgress:
        graph_digest = workflow_graph_digest(graph)
        existing = self._store.load(workflow_run_id)
        if existing is not None:
            if existing.graph_digest != graph_digest:
                raise ValueError("workflow graph differs from durable workflow identity")
            return existing
        candidate = WorkflowProgress(workflow_run_id, graph_digest, 0)
        try:
            return self._store.create(candidate)
        except WorkflowProgressConflict:
            existing = self._store.load(workflow_run_id)
            if existing is None:
                raise
            if existing.graph_digest != graph_digest:
                raise ValueError("workflow graph differs from durable workflow identity")
            return existing

    def require(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress:
        progress = self._store.load(workflow_run_id)
        if progress is None:
            raise KeyError(f"workflow progress not found: {workflow_run_id.value}")
        return progress

    @staticmethod
    def _require_graph(progress: WorkflowProgress, graph: WorkflowGraph) -> None:
        if progress.graph_digest != workflow_graph_digest(graph):
            raise ValueError("workflow graph differs from durable workflow identity")

    def ready_steps(self, workflow_run_id: WorkflowRunId, graph: WorkflowGraph) -> tuple[str, ...]:
        progress = self.require(workflow_run_id)
        self._require_graph(progress, graph)
        if progress.cancellation_requested or progress.failed is not None:
            return ()
        occupied = frozenset(item.step_id for item in (*progress.running, *progress.uncertain))
        return graph.ready_steps(frozenset(progress.completed_steps), occupied)

    def claim(
        self,
        workflow_run_id: WorkflowRunId,
        graph: WorkflowGraph,
        step_id: str,
        operation_id: OperationId,
    ) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        self._require_graph(progress, graph)
        if progress.cancellation_requested or progress.failed is not None:
            raise RuntimeError(f"workflow step is not ready: {step_id}")
        occupied = frozenset(item.step_id for item in (*progress.running, *progress.uncertain))
        ready = graph.ready_steps(frozenset(progress.completed_steps), occupied)
        if step_id not in ready:
            raise RuntimeError(f"workflow step is not ready: {step_id}")
        operation = self._operations.require(operation_id)
        binding = WorkflowOperationBinding(
            step_id, operation_id, operation.effect_id,
            operation.effect_request_id, operation.effect_request_digest,
        )
        updated = replace(progress, version=progress.version + 1, running=progress.running + (binding,))
        return self._store.compare_and_swap(progress.version, updated)

    @staticmethod
    def _require_binding(
        bindings: tuple[WorkflowOperationBinding, ...], step_id: str, operation_id: OperationId, *, state: str
    ) -> WorkflowOperationBinding:
        matches = tuple(item for item in bindings if item.step_id == step_id)
        if len(matches) != 1:
            raise RuntimeError(f"workflow step is not {state}: {step_id}")
        binding = matches[0]
        if binding.operation_id != operation_id:
            raise RuntimeError(
                f"stale workflow operation completion rejected: step={step_id} "
                f"expected={binding.operation_id.value} actual={operation_id.value}"
            )
        return binding

    def _require_operation_identity(self, binding: WorkflowOperationBinding):
        operation = self._operations.require(binding.operation_id)
        durable = (operation.effect_id, operation.effect_request_id, operation.effect_request_digest)
        bound = (binding.effect_id, binding.effect_request_id, binding.effect_request_digest)
        if durable != bound:
            raise RuntimeError(
                f"durable workflow/operation effect identity mismatch: {binding.operation_id.value}"
            )
        return operation

    def complete(self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        binding = self._require_binding(progress.running, step_id, operation_id, state="running")
        operation = self._require_operation_identity(binding)
        if operation.state is not OperationState.COMPLETED:
            raise RuntimeError(f"workflow step operation is not completed: {operation_id.value}")
        updated = replace(
            progress,
            version=progress.version + 1,
            running=tuple(item for item in progress.running if item != binding),
            completed=tuple(sorted((*progress.completed, binding), key=lambda item: item.step_id)),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def fail(self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        if progress.failed is not None:
            if progress.failed.step_id == step_id and progress.failed.operation_id == operation_id:
                return progress
            raise RuntimeError(f"workflow already failed at step: {progress.failed.step_id}")
        active = progress.running + progress.uncertain
        binding = self._require_binding(active, step_id, operation_id, state="active/uncertain")
        updated = replace(
            progress,
            version=progress.version + 1,
            failed=binding,
            running=tuple(item for item in progress.running if item != binding),
            uncertain=tuple(item for item in progress.uncertain if item != binding),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def recover_interrupted(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        if not progress.running:
            return progress
        updated = replace(
            progress,
            version=progress.version + 1,
            uncertain=tuple(sorted((*progress.uncertain, *progress.running), key=lambda item: item.step_id)),
            running=(),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def retry_interrupted_effect_free(
        self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId
    ) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        binding = self._require_binding(progress.uncertain, step_id, operation_id, state="uncertain")
        operation = self._require_operation_identity(binding)
        if operation.effect_profile is not OperationEffectProfile.NONE:
            raise RuntimeError("effectful interrupted workflow step requires authoritative reconciliation proof")
        recovered = self._operations.recover_interrupted(operation_id)
        if recovered.effect_profile is not OperationEffectProfile.NONE:
            raise RuntimeError("effect-free workflow recovery observed mutable operation effect identity")
        remaining = tuple(item for item in progress.uncertain if item != binding)
        updated = replace(progress, version=progress.version + 1, uncertain=remaining)
        return self._store.compare_and_swap(progress.version, updated)

    def reconcile(
        self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId,
        proof: EffectReconciliationProof,
    ) -> WorkflowProgress:
        if not isinstance(proof, EffectReconciliationProof):
            raise TypeError("workflow reconciliation requires EffectReconciliationProof")
        progress = self.require(workflow_run_id)
        binding = self._require_binding(progress.uncertain, step_id, operation_id, state="uncertain")
        operation = self._require_operation_identity(binding)
        if operation.effect_profile is OperationEffectProfile.NONE:
            raise RuntimeError("effect-free interrupted workflow step must use retry_interrupted_effect_free")
        if proof.request_id != binding.effect_request_id:
            raise ValueError("workflow reconciliation request_id does not match durable effect binding")
        resolved = self._operations.reconcile_effect(operation_id, proof)
        if proof.disposition is EffectReconciliationDisposition.UNKNOWN:
            return progress
        remaining = tuple(item for item in progress.uncertain if item != binding)
        if proof.disposition is EffectReconciliationDisposition.APPLIED:
            if resolved.state is not OperationState.COMPLETED:
                resolved = self._operations.complete(operation_id)
            if resolved.state is not OperationState.COMPLETED or resolved.effect_certainty is not OperationEffectCertainty.EXECUTED:
                raise RuntimeError("applied reconciliation did not produce completed executed operation authority")
            updated = replace(
                progress, version=progress.version + 1, uncertain=remaining,
                completed=tuple(sorted((*progress.completed, binding), key=lambda item: item.step_id)),
            )
        elif proof.disposition is EffectReconciliationDisposition.NOT_APPLIED:
            if resolved.effect_certainty is not OperationEffectCertainty.NOT_EXECUTED or resolved.state not in {OperationState.RECOVERING, OperationState.CANCELLED}:
                raise RuntimeError("not-applied reconciliation did not produce retry-safe operation authority")
            updated = replace(progress, version=progress.version + 1, uncertain=remaining)
        elif proof.disposition is EffectReconciliationDisposition.REJECTED:
            if resolved.state is not OperationState.FAILED:
                raise RuntimeError("rejected reconciliation did not produce failed operation authority")
            if progress.failed is not None:
                raise RuntimeError(f"workflow already failed at step: {progress.failed.step_id}")
            updated = replace(progress, version=progress.version + 1, uncertain=remaining, failed=binding)
        else:
            raise RuntimeError("unhandled effect reconciliation disposition")
        return self._store.compare_and_swap(progress.version, updated)

    def request_cancel(
        self, workflow_run_id: WorkflowRunId, reason: str
    ) -> tuple[WorkflowProgress, tuple[OperationId, ...]]:
        if not isinstance(reason, str):
            raise TypeError("workflow cancellation reason must be text")
        reason = reason.strip()
        if not reason:
            raise ValueError("workflow cancellation reason required")
        progress = self.require(workflow_run_id)
        active = (*progress.running, *progress.uncertain)
        if progress.cancellation_requested:
            return progress, tuple(item.operation_id for item in active)
        updated = replace(
            progress,
            version=progress.version + 1,
            cancellation_requested=True,
            cancellation_reason=reason,
        )
        saved = self._store.compare_and_swap(progress.version, updated)
        return saved, tuple(item.operation_id for item in (*saved.running, *saved.uncertain))


__all__ = ["WorkflowProgressOwner", "workflow_graph_digest"]
