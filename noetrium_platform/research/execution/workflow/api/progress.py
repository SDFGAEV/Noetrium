from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

from noetrium_platform.research.execution.operation.api import EffectId, OperationId


def _optional_binding_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"workflow binding {field} must be non-empty text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class WorkflowRunId:
    value: str
    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("workflow_run_id must be text")
        value = self.value.strip()
        if not value:
            raise ValueError("workflow_run_id required")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class WorkflowOperationBinding:
    step_id: str
    operation_id: OperationId
    effect_id: EffectId | None = None
    effect_request_id: str | None = None
    effect_request_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str):
            raise TypeError("workflow binding step_id must be text")
        step_id = self.step_id.strip()
        if not step_id:
            raise ValueError("workflow binding step_id required")
        if not isinstance(self.operation_id, OperationId):
            raise TypeError("workflow binding operation_id must be OperationId")
        if self.effect_id is not None and not isinstance(self.effect_id, EffectId):
            raise TypeError("workflow binding effect_id must be EffectId or null")
        request_id = _optional_binding_text(self.effect_request_id, "effect_request_id")
        request_digest = _optional_binding_text(self.effect_request_digest, "effect_request_digest")
        if self.effect_id is None:
            if request_id is not None or request_digest is not None:
                raise ValueError("workflow binding effect identity must be all-present or all-null")
        elif request_id is None or request_digest is None:
            raise ValueError("workflow binding effect identity must be all-present or all-null")
        object.__setattr__(self, "effect_request_id", request_id)
        object.__setattr__(self, "effect_request_digest", request_digest)
        object.__setattr__(self, "step_id", step_id)


@dataclass(frozen=True, slots=True)
class WorkflowProgress:
    workflow_run_id: WorkflowRunId
    graph_digest: str
    version: int
    completed: tuple[WorkflowOperationBinding, ...] = ()
    running: tuple[WorkflowOperationBinding, ...] = ()
    uncertain: tuple[WorkflowOperationBinding, ...] = ()
    failed: WorkflowOperationBinding | None = None
    cancellation_requested: bool = False
    cancellation_reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("workflow progress version must be integer")
        if self.version < 0:
            raise ValueError("workflow progress version cannot be negative")
        if not isinstance(self.graph_digest, str):
            raise TypeError("workflow graph digest must be text")
        digest = self.graph_digest.strip().lower()
        if not _SHA256.fullmatch(digest):
            raise ValueError("workflow graph digest must be SHA-256 hex")
        object.__setattr__(self, "graph_digest", digest)
        groups = (self.completed, self.running, self.uncertain)
        if any(not isinstance(item, WorkflowOperationBinding) for group in groups for item in group):
            raise TypeError("workflow progress bindings must be WorkflowOperationBinding")
        if self.failed is not None and not isinstance(self.failed, WorkflowOperationBinding):
            raise TypeError("workflow failed binding must be WorkflowOperationBinding")
        bindings = tuple(item for group in groups for item in group)
        if self.failed is not None:
            bindings += (self.failed,)
        step_ids = tuple(item.step_id for item in bindings)
        operation_ids = tuple(item.operation_id for item in bindings)
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("workflow step cannot occupy multiple progress states")
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError("workflow operation identity cannot bind multiple steps")
        if not isinstance(self.cancellation_requested, bool):
            raise TypeError("workflow cancellation_requested must be bool")
        if self.cancellation_reason is not None and not isinstance(self.cancellation_reason, str):
            raise TypeError("workflow cancellation reason must be text or null")
        reason = None if self.cancellation_reason is None else self.cancellation_reason.strip()
        if self.cancellation_requested and not reason:
            raise ValueError("workflow cancellation requires reason")
        if not self.cancellation_requested and reason is not None:
            raise ValueError("workflow cancellation reason requires cancellation_requested")
        object.__setattr__(self, "cancellation_reason", reason)

    @property
    def completed_steps(self) -> tuple[str, ...]:
        return tuple(item.step_id for item in self.completed)

    @property
    def failed_step(self) -> str | None:
        return None if self.failed is None else self.failed.step_id


class WorkflowProgressConflict(RuntimeError): pass
class WorkflowProgressCorruption(RuntimeError): pass


class WorkflowProgressStorePort(Protocol):
    @property
    def durability(self) -> str: ...
    def create(self, progress: WorkflowProgress) -> WorkflowProgress: ...
    def load(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress | None: ...
    def compare_and_swap(self, expected_version: int, progress: WorkflowProgress) -> WorkflowProgress: ...


__all__ = ["WorkflowOperationBinding", "WorkflowProgress", "WorkflowProgressConflict",
           "WorkflowProgressCorruption", "WorkflowProgressStorePort", "WorkflowRunId"]
