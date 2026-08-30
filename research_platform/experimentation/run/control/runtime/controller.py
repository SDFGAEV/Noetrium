from __future__ import annotations

from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.experimentation.run.api.artifacts import RunArtifactVerificationPort
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.run.manifest.api import RunLaunchManifest
from research_platform.experimentation.run.manifest.api.evidence import EvidenceBundleReceipt
from research_platform.platform.kernel import canonical_digest
from research_platform.execution.operation.api import (
    EffectReconciliationOutcome,
    EffectReconciliationVerdict,
)

from ..api.contracts import (
    RunControlAction,
    RunControlActionFailure,
    RunControlCheckpointStorePort,
    RunControlConflict,
    RunControlEvidencePort,
    RunControlIntegrityError,
    RunControlLedgerPort,
    RunControlLifecyclePort,
    RunControlNotFound,
    RunControlOperationIntent,
    RunControlPhase,
    RunControlPreparedOperation,
    RunControlProjection,
    RunControlReceipt,
    RunEvidenceValidity,
    RunExecutionOutcome,
    RunOutcomeProjection,
    RunScientificValidity,
    RunTaskOutcome,
    RunControlReconciliationPort,
    RunControlRequest,
    RunControlTransitionOutcome,
)


_EXECUTION_OUTCOME_BY_PHASE = {
    RunControlPhase.RUNNING: RunExecutionOutcome.IN_PROGRESS,
    RunControlPhase.STOPPED: RunExecutionOutcome.STOPPED,
    RunControlPhase.RECOVERY_REQUIRED: RunExecutionOutcome.RECOVERY_REQUIRED,
    RunControlPhase.COMPLETED: RunExecutionOutcome.SUCCEEDED,
    RunControlPhase.FAILED: RunExecutionOutcome.FAILED,
}


class DurableRunControl:
    """Prepared-before-effect durable run lifecycle authority."""

    def __init__(
        self,
        *,
        identity: RunIdentity,
        manifest: RunLaunchManifest,
        ledger: RunControlLedgerPort,
        lifecycle: RunControlLifecyclePort,
        checkpoint_store: RunControlCheckpointStorePort,
        reconciliation: RunControlReconciliationPort,
        evidence: RunControlEvidencePort,
        artifact_verifier: RunArtifactVerificationPort,
    ) -> None:
        if type(identity) is not RunIdentity:
            raise ValueError("run control identity must be RunIdentity")
        if type(manifest) is not RunLaunchManifest:
            raise ValueError("run control manifest must be RunLaunchManifest")
        self.identity = identity
        self.manifest = manifest
        self.run_identity_digest = identity.digest()
        self.run_manifest_digest = manifest.digest()
        self._ledger = ledger
        self._lifecycle = lifecycle
        self._checkpoint_store = checkpoint_store
        self._reconciliation = reconciliation
        self._evidence = evidence
        self._artifact_verifier = artifact_verifier
        if ledger.run_id != identity.run_id:
            raise ValueError("run control ledger run_id does not match identity")
        if ledger.run_identity_digest != self.run_identity_digest:
            raise ValueError("run control ledger identity digest does not match identity")
        if ledger.run_manifest_digest != self.run_manifest_digest:
            raise ValueError("run control ledger manifest digest does not match manifest")

    def _require_target(self, request: RunControlRequest) -> None:
        target = request.target
        if target.run_id != self.identity.run_id:
            raise RunControlConflict("run control target belongs to a different run")
        if target.run_manifest_digest != self.run_manifest_digest:
            raise RunControlConflict("run control target manifest digest drifted")

    def _receipt(
        self,
        request: RunControlRequest,
        projection: RunControlProjection,
        *,
        evidence_receipt: EvidenceBundleReceipt | None = None,
    ) -> RunControlReceipt:
        return RunControlReceipt(
            action=request.action,
            run_id=self.identity.run_id,
            run_identity_digest=self.run_identity_digest,
            run_manifest_digest=self.run_manifest_digest,
            phase=projection.phase,
            control_generation=projection.control_generation,
            latest_checkpoint_id=projection.latest_checkpoint_id,
            checkpoint_manifest_digest=projection.checkpoint_manifest_digest,
            evidence_bundle_receipt=evidence_receipt,
            outcomes=RunOutcomeProjection(
                _EXECUTION_OUTCOME_BY_PHASE[projection.phase],
                RunTaskOutcome.NOT_EVALUATED,
                (
                    RunEvidenceValidity.FINALIZED_VALID
                    if evidence_receipt is not None
                    else RunEvidenceValidity.NOT_FINALIZED
                    if request.action is RunControlAction.EVIDENCE
                    else RunEvidenceValidity.NOT_OBSERVED
                ),
                RunScientificValidity.NOT_EVALUATED,
            ),
            control_event_receipt=projection.event_receipt,
        )

    @staticmethod
    def _require_outcome(
        outcome: RunControlTransitionOutcome,
        *,
        allowed: frozenset[RunControlPhase],
        action: RunControlAction,
    ) -> RunControlPhase:
        if type(outcome) is not RunControlTransitionOutcome or outcome.phase not in allowed:
            raise RunControlIntegrityError(
                f"run control lifecycle returned invalid {action.value} outcome"
            )
        return outcome.phase

    def _operation_id(
        self,
        request: RunControlRequest,
        *,
        checkpoint_manifest_digest: str | None = None,
    ) -> str:
        cycle = request.restore_cycle_identity
        return canonical_digest({
            "schema_version": "1",
            "run_id": self.identity.run_id,
            "run_identity_digest": self.run_identity_digest,
            "run_manifest_digest": self.run_manifest_digest,
            "action": request.action.value,
            "base_generation": request.target.expected_generation,
            "restore_checkpoint_id": request.restore_checkpoint_id,
            "restore_checkpoint_manifest_digest": checkpoint_manifest_digest,
            "restore_cycle_identity_digest": None if cycle is None else cycle.digest(),
        })

    def _inspect(self, request: RunControlRequest) -> RunControlReceipt:
        projection = self._ledger.read(expected_generation=request.target.expected_generation)
        if projection is None:
            raise RunControlNotFound("run control state does not exist")
        return self._receipt(request, projection)

    def _load_restore_checkpoint(
        self,
        checkpoint_id: str,
        cycle: DecisionCycleIdentity,
    ):
        from research_platform.experimentation.checkpoint.api.contracts import RunCheckpointManifest

        try:
            bundle = self._checkpoint_store.load(checkpoint_id)
        except BaseException as exc:
            raise RunControlIntegrityError("run control restore checkpoint cannot be loaded") from exc
        checkpoint = bundle.manifest
        if type(checkpoint) is not RunCheckpointManifest:
            raise RunControlIntegrityError("run control checkpoint store returned an invalid manifest type")
        if checkpoint.checkpoint_id != checkpoint_id:
            raise RunControlIntegrityError("run control checkpoint id does not match requested checkpoint")
        if checkpoint.run_id != self.identity.run_id or checkpoint.session_id != self.identity.session_id:
            raise RunControlIntegrityError("run control checkpoint belongs to a different run/session")
        if checkpoint.experiment_spec_digest != self.manifest.experiment_spec_digest:
            raise RunControlIntegrityError("run control checkpoint experiment identity drifted")
        expected_cycle_identity = (
            self.identity.run_id,
            self.identity.session_id,
            self.identity.trace_id,
            checkpoint.decision_cycle_id,
        )
        actual_cycle_identity = (
            cycle.run_id,
            cycle.session_id,
            cycle.trace_id,
            cycle.decision_cycle_id,
        )
        if actual_cycle_identity != expected_cycle_identity:
            raise RunControlIntegrityError("run control restore cycle belongs to a different run/checkpoint")
        if checkpoint.cycle_identity_digest != cycle.digest():
            raise RunControlIntegrityError("run control restore cycle digest does not match checkpoint")
        return checkpoint

    def _prepare(
        self,
        request: RunControlRequest,
        *,
        checkpoint_manifest_digest: str | None = None,
    ):
        expected = request.target.expected_generation
        assert expected is not None
        operation_id = self._operation_id(
            request,
            checkpoint_manifest_digest=checkpoint_manifest_digest,
        )
        cycle = request.restore_cycle_identity
        intent = RunControlOperationIntent(
            operation_id=operation_id,
            action=request.action,
            base_generation=expected,
            restore_checkpoint_id=request.restore_checkpoint_id,
            restore_checkpoint_manifest_digest=checkpoint_manifest_digest,
            restore_cycle_identity_digest=None if cycle is None else cycle.digest(),
        )
        return self._ledger.prepare(intent)

    def _commit_or_recover(
        self,
        request: RunControlRequest,
        prepared: RunControlPreparedOperation,
        *,
        phase: RunControlPhase,
        latest_checkpoint_id: str | None,
        checkpoint_manifest_digest: str | None,
    ) -> RunControlReceipt:
        if phase is RunControlPhase.RECOVERY_REQUIRED:
            projection = self._ledger.read()
            if projection is None:
                raise RunControlIntegrityError("prepared run control authority disappeared")
            return self._receipt(request, projection)
        try:
            projection = self._ledger.commit(
                prepared.operation_id,
                phase=phase,
                latest_checkpoint_id=latest_checkpoint_id,
                checkpoint_manifest_digest=checkpoint_manifest_digest,
            )
            return self._receipt(request, projection)
        except BaseException as exc:
            # The terminal publication may have crossed its atomic commit point before
            # the caller observed an error. Re-read authority before classifying it.
            try:
                projection = self._ledger.read()
            except BaseException:
                raise RunControlIntegrityError(
                    "run control terminal publication failed and durable authority cannot be reconstructed"
                ) from exc
            if projection is None:
                raise RunControlIntegrityError(
                    "run control terminal publication lost its prepared authority"
                ) from exc
            receipt = self._receipt(request, projection)
            if projection.pending_operation is not None:
                raise RunControlActionFailure(receipt) from exc
            if projection.event_receipt.operation_id != prepared.operation_id:
                raise RunControlIntegrityError(
                    "run control terminal publication resolved a different operation"
                ) from exc
            return receipt

    def _effectful_run(self, request: RunControlRequest) -> RunControlReceipt:
        existing = self._ledger.read(expected_generation=request.target.expected_generation)
        if existing is not None and existing.pending_operation is None and existing.phase is RunControlPhase.RUNNING:
            return self._receipt(request, existing)
        preparation = self._prepare(request)
        if not preparation.created:
            return self._receipt(request, preparation.projection)
        prepared = preparation.prepared_operation
        try:
            phase = self._require_outcome(
                self._lifecycle.run(
                    self.identity,
                    self.manifest,
                    operation_id=prepared.operation_id,
                ),
                allowed=frozenset({
                    RunControlPhase.RUNNING,
                    RunControlPhase.RECOVERY_REQUIRED,
                    RunControlPhase.FAILED,
                }),
                action=RunControlAction.RUN,
            )
        except BaseException as exc:
            projection = self._ledger.read()
            if projection is None:
                raise RunControlIntegrityError("run control prepared authority disappeared after run failure") from exc
            raise RunControlActionFailure(self._receipt(request, projection)) from exc
        return self._commit_or_recover(
            request,
            prepared,
            phase=phase,
            latest_checkpoint_id=prepared.base_latest_checkpoint_id,
            checkpoint_manifest_digest=prepared.base_checkpoint_manifest_digest,
        )

    def _effectful_stop(self, request: RunControlRequest) -> RunControlReceipt:
        existing = self._ledger.read(expected_generation=request.target.expected_generation)
        if existing is None:
            raise RunControlNotFound("run control state does not exist")
        if existing.pending_operation is None and existing.phase in {
            RunControlPhase.STOPPED,
            RunControlPhase.COMPLETED,
        }:
            return self._receipt(request, existing)
        preparation = self._prepare(request)
        if not preparation.created:
            return self._receipt(request, preparation.projection)
        prepared = preparation.prepared_operation
        try:
            phase = self._require_outcome(
                self._lifecycle.stop(
                    self.identity,
                    self.manifest,
                    operation_id=prepared.operation_id,
                ),
                allowed=frozenset({
                    RunControlPhase.STOPPED,
                    RunControlPhase.COMPLETED,
                    RunControlPhase.RECOVERY_REQUIRED,
                    RunControlPhase.FAILED,
                }),
                action=RunControlAction.STOP,
            )
        except BaseException as exc:
            projection = self._ledger.read()
            if projection is None:
                raise RunControlIntegrityError("run control prepared authority disappeared after stop failure") from exc
            raise RunControlActionFailure(self._receipt(request, projection)) from exc
        return self._commit_or_recover(
            request,
            prepared,
            phase=phase,
            latest_checkpoint_id=prepared.base_latest_checkpoint_id,
            checkpoint_manifest_digest=prepared.base_checkpoint_manifest_digest,
        )

    def _effectful_resume(self, request: RunControlRequest) -> RunControlReceipt:
        checkpoint_id = request.restore_checkpoint_id
        cycle = request.restore_cycle_identity
        assert checkpoint_id is not None and cycle is not None
        checkpoint = self._load_restore_checkpoint(checkpoint_id, cycle)
        checkpoint_digest = checkpoint.digest()
        existing = self._ledger.read(expected_generation=request.target.expected_generation)
        if existing is None:
            raise RunControlNotFound("run control state does not exist")
        if (
            existing.pending_operation is None
            and existing.phase is RunControlPhase.RUNNING
            and existing.latest_checkpoint_id == checkpoint.checkpoint_id
            and existing.checkpoint_manifest_digest == checkpoint_digest
        ):
            return self._receipt(request, existing)
        preparation = self._prepare(
            request,
            checkpoint_manifest_digest=checkpoint_digest,
        )
        if not preparation.created:
            return self._receipt(request, preparation.projection)
        prepared = preparation.prepared_operation
        try:
            phase = self._require_outcome(
                self._lifecycle.resume(
                    self.identity,
                    self.manifest,
                    checkpoint,
                    cycle,
                    operation_id=prepared.operation_id,
                ),
                allowed=frozenset({
                    RunControlPhase.RUNNING,
                    RunControlPhase.RECOVERY_REQUIRED,
                    RunControlPhase.FAILED,
                }),
                action=RunControlAction.RESUME,
            )
        except BaseException as exc:
            projection = self._ledger.read()
            if projection is None:
                raise RunControlIntegrityError("run control prepared authority disappeared after resume failure") from exc
            raise RunControlActionFailure(self._receipt(request, projection)) from exc
        return self._commit_or_recover(
            request,
            prepared,
            phase=phase,
            latest_checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_manifest_digest=checkpoint_digest,
        )

    def _resolved_reconciliation_phase(
        self,
        pending: RunControlPreparedOperation,
        verdict: EffectReconciliationVerdict,
    ) -> RunControlPhase | None:
        if type(verdict) is not EffectReconciliationVerdict:
            raise RunControlIntegrityError("run control reconciliation provider returned invalid verdict")
        if verdict.request_id != pending.operation_id:
            raise RunControlIntegrityError("run control reconciliation request_id does not match pending operation")
        if verdict.outcome is EffectReconciliationOutcome.UNKNOWN or verdict.verification_required:
            return None
        if verdict.request_digest != pending.operation_id:
            raise RunControlIntegrityError("run control reconciliation request digest does not match pending operation")
        if verdict.outcome is EffectReconciliationOutcome.EXECUTED:
            return {
                RunControlAction.RUN: RunControlPhase.RUNNING,
                RunControlAction.STOP: RunControlPhase.STOPPED,
                RunControlAction.RESUME: RunControlPhase.RUNNING,
            }[pending.action]
        if verdict.outcome is EffectReconciliationOutcome.NOT_EXECUTED:
            if pending.action is RunControlAction.RUN and pending.base_phase is None:
                return RunControlPhase.FAILED
            return pending.base_phase or RunControlPhase.FAILED
        if verdict.outcome is EffectReconciliationOutcome.REJECTED:
            if pending.action is RunControlAction.RUN:
                return RunControlPhase.FAILED
            return pending.base_phase or RunControlPhase.FAILED
        raise RunControlIntegrityError("run control reconciliation verdict is unsupported")

    def _reconcile(self, request: RunControlRequest) -> RunControlReceipt:
        projection = self._ledger.read(expected_generation=request.target.expected_generation)
        if projection is None:
            raise RunControlNotFound("run control state does not exist")
        pending = projection.pending_operation
        if pending is None:
            if projection.phase is RunControlPhase.RUNNING:
                return self._receipt(request, projection)
            raise RunControlConflict("run control has no unresolved prepared operation")
        proof = self._reconciliation.reconcile(self.identity, self.manifest, pending)
        phase = self._resolved_reconciliation_phase(pending, proof)
        if phase is None:
            return self._receipt(request, projection)
        checkpoint_id = pending.base_latest_checkpoint_id
        checkpoint_digest = pending.base_checkpoint_manifest_digest
        if pending.action is RunControlAction.RESUME and phase is RunControlPhase.RUNNING:
            checkpoint_id = pending.restore_checkpoint_id
            checkpoint_digest = pending.restore_checkpoint_manifest_digest
        return self._commit_or_recover(
            request,
            pending,
            phase=phase,
            latest_checkpoint_id=checkpoint_id,
            checkpoint_manifest_digest=checkpoint_digest,
        )

    def _evidence_receipt(self, request: RunControlRequest) -> RunControlReceipt:
        projection = self._ledger.read(expected_generation=request.target.expected_generation)
        if projection is None:
            raise RunControlNotFound("run control state does not exist")
        receipt = self._evidence.evidence(self.identity, self.manifest)
        if receipt is not None:
            if type(receipt) is not EvidenceBundleReceipt:
                raise RunControlIntegrityError("run control evidence provider returned an invalid receipt")
            if receipt.run_id != self.identity.run_id or receipt.run_manifest_digest != self.run_manifest_digest:
                raise RunControlIntegrityError("run control evidence receipt belongs to a different run/manifest")
            try:
                self._artifact_verifier.verify_finalized(receipt.manifest_artifact_receipt)
            except BaseException as exc:
                raise RunControlIntegrityError("run control evidence manifest is not finalized authority") from exc
        return self._receipt(request, projection, evidence_receipt=receipt)

    def execute(self, request: RunControlRequest) -> RunControlReceipt:
        if type(request) is not RunControlRequest:
            raise ValueError("run control execute requires RunControlRequest")
        self._require_target(request)
        if request.action is RunControlAction.INSPECT:
            return self._inspect(request)
        if request.action is RunControlAction.RUN:
            return self._effectful_run(request)
        if request.action is RunControlAction.STOP:
            return self._effectful_stop(request)
        if request.action is RunControlAction.RESUME:
            return self._effectful_resume(request)
        if request.action is RunControlAction.RECONCILE:
            return self._reconcile(request)
        if request.action is RunControlAction.EVIDENCE:
            return self._evidence_receipt(request)
        raise RunControlIntegrityError("run control action is unsupported")


__all__ = ["DurableRunControl"]
