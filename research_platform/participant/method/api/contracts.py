from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import math
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel.context import ExecutionContext
from research_platform.platform.kernel import JsonValue, require_sha256


@dataclass(frozen=True, slots=True)
class MethodIdentity:
    method_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str | None = None

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (self.method_id, self.implementation_version, self.abi_version, self.schema_version)):
            raise ValueError("method identity fields must be non-empty text")
        if self.artifact_digest is not None:
            require_sha256(self.artifact_digest, "method artifact_digest")


@dataclass(frozen=True, slots=True)
class MethodSnapshot:
    method_id: str
    implementation_version: str
    schema_version: str
    method_runtime_binding_digest: str
    session_id: str
    payload_sha256: str
    opaque_payload: bytes


@dataclass(frozen=True, slots=True)
class RecallRequest:
    intent: str
    context: ExecutionContext
    limit: int = 8


@dataclass(frozen=True, slots=True)
class RecallResult:
    context_text: str
    method_generation: str
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodTaskOutcome(Mapping[str, JsonValue]):
    """Portable task outcome exposed to a method at the completion boundary.

    Workload/environment implementations may own richer receipts, but method
    implementations should not depend on those concrete types.  The mapping
    behavior preserves the pre-v1 opaque-result ABI while providing a stable
    typed surface to methods that need scientific task feedback.
    """

    task_id: str
    family: str
    lineage_id: str
    success: bool
    utility: float
    steps: int
    failure_reason: str = ""
    memory_queries: int = 0

    _KEYS = (
        "task_id",
        "family",
        "lineage_id",
        "success",
        "utility",
        "steps",
        "failure_reason",
        "memory_queries",
    )

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.family.strip() or not self.lineage_id.strip():
            raise ValueError("method task outcome identity fields must be non-empty")
        if not isinstance(self.success, bool):
            raise TypeError("method task outcome success must be boolean")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.steps, self.memory_queries)
        ):
            raise ValueError("method task outcome counts must be non-negative integers")
        if not isinstance(self.failure_reason, str):
            raise TypeError("method task outcome failure_reason must be text")
        if not math.isfinite(float(self.utility)):
            raise ValueError("method task outcome utility must be finite")

    def __getitem__(self, key: str) -> JsonValue:
        if key not in self._KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._KEYS)

    def __len__(self) -> int:
        return len(self._KEYS)


@dataclass(frozen=True, slots=True)
class MethodTaskCompletionReceipt:
    completion_key: str
    method_generation: str | None = None
    artifacts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.completion_key.strip():
            raise ValueError("completion_key must be non-empty")


@runtime_checkable
class IdempotentTaskCompletionSession(Protocol):
    """Optional capability required by crash-durable cross-component recovery."""

    task_completion_idempotency: str
    def task_completion_key(self, context: ExecutionContext) -> str: ...


@runtime_checkable
class TaskCompletionReconciliationSession(Protocol):
    """Optional stronger capability for COMMIT_ONLY crash recovery.

    The implementation may reconcile local session state from its own authoritative
    method state, but it must never execute a new task completion.  ``None`` means
    the method cannot prove that the completion key was committed.
    """

    def reconcile_task_completion(
        self, completion_key: str, context: ExecutionContext
    ) -> MethodTaskCompletionReceipt | None: ...


@runtime_checkable
class MethodSession(Protocol):
    def recall(self, request: RecallRequest) -> RecallResult: ...
    def ingest(self, evidence: JsonValue, context: ExecutionContext) -> None: ...
    def task_completed(self, result: JsonValue, context: ExecutionContext) -> MethodTaskCompletionReceipt | None: ...
    def checkpoint(self) -> MethodSnapshot: ...
    def restore(self, snapshot: MethodSnapshot) -> None: ...
    def diagnostics(self) -> Mapping[str, JsonValue]: ...
    def close(self) -> None: ...
