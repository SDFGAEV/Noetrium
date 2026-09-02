from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Protocol

from research_platform.platform.kernel import canonical_digest

from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.run.manifest.api import RunLaunchManifest
from research_platform.experimentation.run.manifest.api.evidence import EvidenceBundleReceipt
from research_platform.execution.operation.api import EffectReconciliationVerdict

if TYPE_CHECKING:
    from research_platform.experimentation.checkpoint.api.contracts import RunCheckpointManifest

_HEX = frozenset("0123456789abcdef")


def _require_text(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_sha256(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{field} must be a canonical lowercase SHA-256")
    return value


def _require_optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field)


class RunControlAction(StrEnum):
    RUN = "run"
    INSPECT = "inspect"
    STOP = "stop"
    RESUME = "resume"
    RECONCILE = "reconcile"
    EVIDENCE = "evidence"


class RunControlPhase(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    RECOVERY_REQUIRED = "recovery_required"
    COMPLETED = "completed"
    FAILED = "failed"


class RunControlRecordKind(StrEnum):
    PREPARED = "prepared"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class RunControlTarget:
    run_id: str
    run_manifest_digest: str
    expected_generation: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run control target run_id")
        _require_sha256(self.run_manifest_digest, "run control target run_manifest_digest")
        if self.expected_generation is not None and (
            type(self.expected_generation) is not int or self.expected_generation < 0
        ):
            raise ValueError("run control target expected_generation must be a non-negative integer or None")


@dataclass(frozen=True, slots=True)
class RunControlRequest:
    action: RunControlAction
    target: RunControlTarget
    restore_checkpoint_id: str | None = None
    restore_cycle_identity: DecisionCycleIdentity | None = None

    def __post_init__(self) -> None:
        if type(self.action) is not RunControlAction:
            raise ValueError("run control action must be RunControlAction")
        if type(self.target) is not RunControlTarget:
            raise ValueError("run control target must be RunControlTarget")
        _require_optional_text(self.restore_checkpoint_id, "run control restore_checkpoint_id")
        if self.restore_cycle_identity is not None and type(self.restore_cycle_identity) is not DecisionCycleIdentity:
            raise ValueError("run control restore_cycle_identity must be DecisionCycleIdentity or None")
        if self.action in {
            RunControlAction.RUN,
            RunControlAction.STOP,
            RunControlAction.RESUME,
            RunControlAction.RECONCILE,
        } and self.target.expected_generation is None:
            raise ValueError("state-changing run control action requires expected_generation")
        if self.action is RunControlAction.RESUME:
            if self.restore_checkpoint_id is None or self.restore_cycle_identity is None:
                raise ValueError("run control resume requires checkpoint id and restore cycle identity")
        elif self.restore_checkpoint_id is not None or self.restore_cycle_identity is not None:
            raise ValueError("run control restore fields are valid only for resume")


@dataclass(frozen=True, slots=True)
class RunControlOperationIntent:
    operation_id: str
    action: RunControlAction
    base_generation: int
    restore_checkpoint_id: str | None = None
    restore_checkpoint_manifest_digest: str | None = None
    restore_cycle_identity_digest: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.operation_id, "run control operation_id")
        if self.action not in {RunControlAction.RUN, RunControlAction.STOP, RunControlAction.RESUME}:
            raise ValueError("run control operation intent must be run/stop/resume")
        if type(self.base_generation) is not int or self.base_generation < 0:
            raise ValueError("run control operation base_generation must be non-negative")
        checkpoint_id = _require_optional_text(self.restore_checkpoint_id, "run control restore_checkpoint_id")
        checkpoint_digest = self.restore_checkpoint_manifest_digest
        cycle_digest = self.restore_cycle_identity_digest
        if self.action is RunControlAction.RESUME:
            if checkpoint_id is None or checkpoint_digest is None or cycle_digest is None:
                raise ValueError("run control resume intent requires exact checkpoint and restore-cycle identity")
            _require_sha256(checkpoint_digest, "run control restore checkpoint manifest digest")
            _require_sha256(cycle_digest, "run control restore cycle identity digest")
        elif checkpoint_id is not None or checkpoint_digest is not None or cycle_digest is not None:
            raise ValueError("run control restore identity is valid only for resume intent")


@dataclass(frozen=True, slots=True)
class RunControlPreparedOperation:
    operation_id: str
    action: RunControlAction
    base_generation: int
    base_phase: RunControlPhase | None
    base_latest_checkpoint_id: str | None
    base_checkpoint_manifest_digest: str | None
    restore_checkpoint_id: str | None
    restore_checkpoint_manifest_digest: str | None
    restore_cycle_identity_digest: str | None
    record_sequence: int
    record_digest: str

    def __post_init__(self) -> None:
        RunControlOperationIntent(
            self.operation_id,
            self.action,
            self.base_generation,
            self.restore_checkpoint_id,
            self.restore_checkpoint_manifest_digest,
            self.restore_cycle_identity_digest,
        )
        if self.base_generation == 0:
            if self.base_phase is not None:
                raise ValueError("generation-zero prepared operation cannot have a base phase")
        elif type(self.base_phase) is not RunControlPhase:
            raise ValueError("prepared operation with durable base generation requires base phase")
        base_checkpoint = _require_optional_text(
            self.base_latest_checkpoint_id, "run control base latest checkpoint id"
        )
        base_digest = self.base_checkpoint_manifest_digest
        if (base_checkpoint is None) != (base_digest is None):
            raise ValueError("prepared operation base checkpoint identity is incomplete")
        if base_digest is not None:
            _require_sha256(base_digest, "run control base checkpoint manifest digest")
        if type(self.record_sequence) is not int or self.record_sequence <= 0:
            raise ValueError("prepared operation record_sequence must be positive")
        _require_sha256(self.record_digest, "prepared operation record digest")


@dataclass(frozen=True, slots=True)
class RunControlEventReceipt:
    run_id: str
    record_sequence: int
    record_kind: RunControlRecordKind
    control_generation: int
    action: RunControlAction
    phase: RunControlPhase
    operation_id: str
    event_digest: str

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run control event run_id")
        if type(self.record_sequence) is not int or self.record_sequence <= 0:
            raise ValueError("run control event record_sequence must be positive")
        if type(self.record_kind) is not RunControlRecordKind:
            raise ValueError("run control event record_kind must be RunControlRecordKind")
        if type(self.control_generation) is not int or self.control_generation < 0:
            raise ValueError("run control event generation must be non-negative")
        if type(self.action) is not RunControlAction:
            raise ValueError("run control event action must be RunControlAction")
        if type(self.phase) is not RunControlPhase:
            raise ValueError("run control event phase must be RunControlPhase")
        _require_sha256(self.operation_id, "run control event operation_id")
        _require_sha256(self.event_digest, "run control event digest")
        if self.record_kind is RunControlRecordKind.PREPARED and self.phase is not RunControlPhase.RECOVERY_REQUIRED:
            raise ValueError("prepared run control event must project recovery_required")


@dataclass(frozen=True, slots=True)
class RunControlProjection:
    run_id: str
    run_identity_digest: str
    run_manifest_digest: str
    phase: RunControlPhase
    control_generation: int
    latest_checkpoint_id: str | None
    checkpoint_manifest_digest: str | None
    event_receipt: RunControlEventReceipt
    pending_operation: RunControlPreparedOperation | None = None


class RunExecutionOutcome(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"
    RECOVERY_REQUIRED = "recovery_required"


class RunTaskOutcome(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunEvidenceValidity(StrEnum):
    NOT_OBSERVED = "not_observed"
    NOT_FINALIZED = "not_finalized"
    FINALIZED_VALID = "finalized_valid"


class RunScientificValidity(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RunOutcomeProjection:
    execution: RunExecutionOutcome
    task: RunTaskOutcome
    evidence: RunEvidenceValidity
    scientific: RunScientificValidity

    def __post_init__(self) -> None:
        expected = (RunExecutionOutcome, RunTaskOutcome, RunEvidenceValidity, RunScientificValidity)
        if tuple(type(value) for value in (self.execution, self.task, self.evidence, self.scientific)) != expected:
            raise ValueError("run outcome projection fields must use their exact typed authorities")


@dataclass(frozen=True, slots=True)
class RunControlReceiptReference:
    """Stable semantic reference for one complete RunControlReceipt."""

    SCHEMA_VERSION: ClassVar[str] = "run-control.receipt.v1"
    schema_version: str
    run_id: str
    record_sequence: int
    receipt_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("run control receipt reference schema is unsupported")
        _require_text(self.run_id, "run control receipt reference run_id")
        if type(self.record_sequence) is not int or self.record_sequence <= 0:
            raise ValueError("run control receipt reference sequence must be positive")
        _require_sha256(self.receipt_digest, "run control receipt reference digest")

    @property
    def key(self) -> str:
        return f"{self.run_id}:{self.record_sequence}:{self.receipt_digest}"


@dataclass(frozen=True, slots=True)
class RunControlReceipt:
    action: RunControlAction
    run_id: str
    run_identity_digest: str
    run_manifest_digest: str
    phase: RunControlPhase
    control_generation: int
    latest_checkpoint_id: str | None
    checkpoint_manifest_digest: str | None
    evidence_bundle_receipt: EvidenceBundleReceipt | None
    outcomes: RunOutcomeProjection
    control_event_receipt: RunControlEventReceipt

    def __post_init__(self) -> None:
        if type(self.action) is not RunControlAction:
            raise ValueError("run control receipt action must be RunControlAction")
        _require_text(self.run_id, "run control receipt run_id")
        _require_sha256(self.run_identity_digest, "run control receipt run_identity_digest")
        _require_sha256(self.run_manifest_digest, "run control receipt run_manifest_digest")
        if type(self.phase) is not RunControlPhase:
            raise ValueError("run control receipt phase must be RunControlPhase")
        if type(self.control_generation) is not int or self.control_generation < 0:
            raise ValueError("run control receipt generation must be non-negative")
        checkpoint_id = _require_optional_text(self.latest_checkpoint_id, "run control latest_checkpoint_id")
        checkpoint_digest = self.checkpoint_manifest_digest
        if (checkpoint_id is None) != (checkpoint_digest is None):
            raise ValueError("run control checkpoint id and manifest digest must be present together")
        if checkpoint_digest is not None:
            _require_sha256(checkpoint_digest, "run control checkpoint_manifest_digest")
        if self.evidence_bundle_receipt is not None and type(self.evidence_bundle_receipt) is not EvidenceBundleReceipt:
            raise ValueError("run control evidence_bundle_receipt must be EvidenceBundleReceipt or None")
        if type(self.outcomes) is not RunOutcomeProjection:
            raise ValueError("run control outcomes must be RunOutcomeProjection")
        expected_execution = {
            RunControlPhase.RUNNING: RunExecutionOutcome.IN_PROGRESS,
            RunControlPhase.STOPPED: RunExecutionOutcome.STOPPED,
            RunControlPhase.RECOVERY_REQUIRED: RunExecutionOutcome.RECOVERY_REQUIRED,
            RunControlPhase.COMPLETED: RunExecutionOutcome.SUCCEEDED,
            RunControlPhase.FAILED: RunExecutionOutcome.FAILED,
        }[self.phase]
        if self.outcomes.execution is not expected_execution:
            raise ValueError("run control execution outcome contradicts lifecycle phase")
        expected_evidence = (
            RunEvidenceValidity.FINALIZED_VALID
            if self.evidence_bundle_receipt is not None
            else RunEvidenceValidity.NOT_FINALIZED
            if self.action is RunControlAction.EVIDENCE
            else RunEvidenceValidity.NOT_OBSERVED
        )
        if self.outcomes.evidence is not expected_evidence:
            raise ValueError("run control evidence validity contradicts finalized evidence authority")
        if self.outcomes.task is not RunTaskOutcome.NOT_EVALUATED:
            raise ValueError("run control receipt cannot claim task outcome authority")
        if self.outcomes.scientific is not RunScientificValidity.NOT_EVALUATED:
            raise ValueError("run control receipt cannot claim scientific validity authority")
        if type(self.control_event_receipt) is not RunControlEventReceipt:
            raise ValueError("run control control_event_receipt must be RunControlEventReceipt")
        event = self.control_event_receipt
        if event.run_id != self.run_id or event.control_generation != self.control_generation or event.phase is not self.phase:
            raise ValueError("run control receipt does not match its authoritative control event")

    @property
    def schema_version(self) -> str:
        return RunControlReceiptReference.SCHEMA_VERSION

    @property
    def receipt_digest(self) -> str:
        return canonical_digest({
            "schema_version": self.schema_version,
            "action": self.action.value,
            "run_id": self.run_id,
            "run_identity_digest": self.run_identity_digest,
            "run_manifest_digest": self.run_manifest_digest,
            "phase": self.phase.value,
            "control_generation": self.control_generation,
            "latest_checkpoint_id": self.latest_checkpoint_id,
            "checkpoint_manifest_digest": self.checkpoint_manifest_digest,
            "evidence_bundle_receipt": (
                self.evidence_bundle_receipt.digest
                if self.evidence_bundle_receipt is not None else None
            ),
            "outcomes": self.outcomes,
            "control_event_receipt": self.control_event_receipt,
        })

    @property
    def reference(self) -> RunControlReceiptReference:
        return RunControlReceiptReference(
            self.schema_version,
            self.run_id,
            self.control_event_receipt.record_sequence,
            self.receipt_digest,
        )


@dataclass(frozen=True, slots=True)
class RunControlTransitionOutcome:
    phase: RunControlPhase

    def __post_init__(self) -> None:
        if type(self.phase) is not RunControlPhase:
            raise ValueError("run control transition outcome phase must be RunControlPhase")


@dataclass(frozen=True, slots=True)
class RunControlPreparation:
    projection: RunControlProjection
    prepared_operation: RunControlPreparedOperation
    created: bool

    def __post_init__(self) -> None:
        if type(self.projection) is not RunControlProjection:
            raise ValueError("run control preparation requires typed projection")
        if type(self.prepared_operation) is not RunControlPreparedOperation:
            raise ValueError("run control preparation requires typed prepared operation")
        if type(self.created) is not bool:
            raise ValueError("run control preparation created flag must be boolean")


class RunControlError(RuntimeError):
    pass


class RunControlNotFound(RunControlError):
    pass


class RunControlConflict(RunControlError):
    pass


class RunControlStaleGeneration(RunControlConflict):
    pass


class RunControlIntegrityError(RunControlError):
    pass


class RunControlActionFailure(RunControlError):
    def __init__(self, receipt: RunControlReceipt) -> None:
        self.receipt = receipt
        super().__init__(
            f"run control {receipt.action.value} entered {receipt.phase.value} at generation {receipt.control_generation}"
        )


class RunControlPort(Protocol):
    def execute(self, request: RunControlRequest) -> RunControlReceipt: ...


class RunControlLedgerPort(Protocol):
    run_id: str
    run_identity_digest: str
    run_manifest_digest: str

    def read(self, *, expected_generation: int | None = None) -> RunControlProjection | None: ...

    def prepare(self, intent: RunControlOperationIntent) -> RunControlPreparation: ...

    def commit(
        self,
        operation_id: str,
        *,
        phase: RunControlPhase,
        latest_checkpoint_id: str | None,
        checkpoint_manifest_digest: str | None,
    ) -> RunControlProjection: ...


class RunControlCheckpointBundlePort(Protocol):
    @property
    def manifest(self) -> "RunCheckpointManifest": ...


class RunControlCheckpointStorePort(Protocol):
    def load(self, checkpoint_id: str) -> RunControlCheckpointBundlePort: ...


class RunControlLifecyclePort(Protocol):
    def run(
        self,
        identity: RunIdentity,
        manifest: RunLaunchManifest,
        *,
        operation_id: str,
    ) -> RunControlTransitionOutcome: ...

    def stop(
        self,
        identity: RunIdentity,
        manifest: RunLaunchManifest,
        *,
        operation_id: str,
    ) -> RunControlTransitionOutcome: ...

    def resume(
        self,
        identity: RunIdentity,
        manifest: RunLaunchManifest,
        checkpoint: "RunCheckpointManifest",
        restore_cycle_identity: DecisionCycleIdentity,
        *,
        operation_id: str,
    ) -> RunControlTransitionOutcome: ...


class RunControlReconciliationPort(Protocol):
    def reconcile(
        self,
        identity: RunIdentity,
        manifest: RunLaunchManifest,
        prepared_operation: RunControlPreparedOperation,
    ) -> EffectReconciliationVerdict: ...


class RunControlEvidencePort(Protocol):
    def evidence(self, identity: RunIdentity, manifest: RunLaunchManifest) -> EvidenceBundleReceipt | None: ...


__all__ = [name for name in globals() if name.startswith("RunControl")]
