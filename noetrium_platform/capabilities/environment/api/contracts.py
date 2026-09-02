from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonInput, JsonValue, canonical_digest
from noetrium_platform.foundation.kernel.kernel.operation import EffectReceipt
from noetrium_platform.infrastructure.reliability.effect.api import PreparedEffectHandle

@dataclass(frozen=True, slots=True)
class SystemIdentity:
    id: str
    version: str = "1"
    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("system id must be non-empty")
        if not self.version.strip():
            raise ValueError("system version must be non-empty")

@dataclass(frozen=True, slots=True)
class SystemSpec:
    identity: SystemIdentity
    purpose: str
    children: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("system purpose must be non-empty")


@dataclass(frozen=True, slots=True)
class EnvironmentIdentity:
    environment_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str = ""


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    generation: str
    payload: JsonInput
    artifact_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    action_type: str
    payload: JsonInput
    context: ExecutionContext


def action_request_digest(request: ActionRequest) -> str:
    """Stable scientific action identity; excludes tracing/span-only fields."""

    context = request.context
    return canonical_digest(
        {
            "action_id": request.action_id,
            "action_type": request.action_type,
            "payload": request.payload,
            "run_id": context.run_id,
            "study_id": context.study_id,
            "lifetime_id": context.lifetime_id,
            "task_id": context.task_id,
            "decision_cycle_id": context.decision_cycle_id,
            "checkpoint_id": context.checkpoint_id,
            "source_generation": context.generation("environment"),
        }
    )


@dataclass(frozen=True, slots=True)
class ActionResult:
    action_id: str
    accepted: bool
    observation: Observation | None
    effect: EffectReceipt | None
    diagnostics: dict[str, JsonValue]


class ActionReconciliationDisposition(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ActionReconciliationResult:
    action_id: str
    disposition: ActionReconciliationDisposition
    result: ActionResult | None
    diagnostics: dict[str, JsonValue]


@runtime_checkable
class DurablePreparedActionSession(Protocol):
    action_recovery_durability: str

    def prepare_action_recovery(
        self, request: ActionRequest, context: ExecutionContext
    ) -> PreparedEffectHandle: ...

    def execute_prepared_action(
        self, request: ActionRequest, handle: PreparedEffectHandle
    ) -> ActionResult: ...

    def reconcile_prepared_action(
        self, handle: PreparedEffectHandle, context: ExecutionContext
    ) -> ActionReconciliationResult: ...


@runtime_checkable
class EnvironmentSession(Protocol):
    def observe(self, context: ExecutionContext) -> Observation: ...
    def act(self, request: ActionRequest) -> ActionResult: ...
    def reconcile(self, effect: EffectReceipt, context: ExecutionContext) -> EffectReceipt: ...
    def checkpoint(self) -> bytes: ...
    def restore(self, payload: bytes) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class EnvironmentImplementation(Protocol):
    @property
    def identity(self) -> EnvironmentIdentity: ...
