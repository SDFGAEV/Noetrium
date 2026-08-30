from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests_support import frozen_runtime_manifest
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.execution.operation.api import project_effect_reconciliation
from research_platform.experimentation.checkpoint.api.contracts import (
    RunCheckpointBundle,
    RunCheckpointManifest,
)
from research_platform.experimentation.run.api.artifacts import (
    RunArtifactKind,
    RunArtifactSnapshotReceipt,
    RunArtifactVerificationError,
)
from research_platform.experimentation.run.control.api import (
    RunControlAction,
    RunControlActionFailure,
    RunControlConflict,
    RunControlIntegrityError,
    RunControlPhase,
    RunControlRequest,
    RunControlStaleGeneration,
    RunControlTarget,
    RunControlTransitionOutcome,
)
from research_platform.experimentation.run.control.providers import DirectoryRunControlLedger
from research_platform.experimentation.run.control.runtime import DurableRunControl
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.run.manifest.api.evidence import EvidenceBundleReceipt
from research_platform.platform.kernel import EffectCertainty, EffectClass, EffectReceipt
from research_platform.reliability.effect.api import (
    EffectReconciliationDisposition,
    EffectReconciliationProof,
)


class _InlineActor:
    actor_id = "run-control-test-inline"

    def call(self, operation, fn, /, *args, **kwargs):
        del operation
        return fn(*args, **kwargs)


class _Lifecycle:
    def __init__(
        self,
        *,
        run_phase: RunControlPhase = RunControlPhase.RUNNING,
        stop_phase: RunControlPhase = RunControlPhase.STOPPED,
        resume_phase: RunControlPhase = RunControlPhase.RUNNING,
        run_error: BaseException | None = None,
        stop_error: BaseException | None = None,
        resume_error: BaseException | None = None,
    ) -> None:
        self.run_phase = run_phase
        self.stop_phase = stop_phase
        self.resume_phase = resume_phase
        self.run_error = run_error
        self.stop_error = stop_error
        self.resume_error = resume_error
        self.run_calls = 0
        self.stop_calls = 0
        self.resume_calls = 0

    def run(self, identity, manifest, *, operation_id):
        del identity, manifest
        assert isinstance(operation_id, str) and len(operation_id) == 64
        self.run_calls += 1
        if self.run_error is not None:
            raise self.run_error
        return RunControlTransitionOutcome(self.run_phase)

    def stop(self, identity, manifest, *, operation_id):
        del identity, manifest
        assert isinstance(operation_id, str) and len(operation_id) == 64
        self.stop_calls += 1
        if self.stop_error is not None:
            raise self.stop_error
        return RunControlTransitionOutcome(self.stop_phase)

    def resume(self, identity, manifest, checkpoint, restore_cycle_identity, *, operation_id):
        del identity, manifest, checkpoint, restore_cycle_identity
        assert isinstance(operation_id, str) and len(operation_id) == 64
        self.resume_calls += 1
        if self.resume_error is not None:
            raise self.resume_error
        return RunControlTransitionOutcome(self.resume_phase)


class _CheckpointStore:
    def __init__(self, manifest: RunCheckpointManifest) -> None:
        self.manifest = manifest
        self.loads = 0

    def load(self, checkpoint_id: str) -> RunCheckpointBundle:
        self.loads += 1
        if checkpoint_id != self.manifest.checkpoint_id:
            raise KeyError(checkpoint_id)
        return RunCheckpointBundle(self.manifest, ())


class _Reconciliation:
    def __init__(self, proof: EffectReconciliationProof) -> None:
        self.proof = proof
        self.calls = 0

    def reconcile(self, identity, manifest, prepared_operation) -> EffectReconciliationProof:
        del identity, manifest
        self.calls += 1
        proof = self.proof
        if proof.request_id == "AUTO":
            effect = proof.effect
            if effect is not None:
                effect = EffectReceipt(
                    effect.effect_id, prepared_operation.operation_id, effect.effect_class,
                    effect.certainty, effect.provider_instance_id, effect.verification_required,
                    effect.before_artifact, effect.after_artifact, effect.provider_receipt,
                )
            proof = EffectReconciliationProof(
                prepared_operation.operation_id, proof.disposition, effect, proof.diagnostics
            )
        return project_effect_reconciliation(proof)


class _Evidence:
    def __init__(self, receipt: EvidenceBundleReceipt | None = None) -> None:
        self.receipt = receipt

    def evidence(self, identity, manifest) -> EvidenceBundleReceipt | None:
        del identity, manifest
        return self.receipt


class _Verifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def verify_finalized(self, receipt: RunArtifactSnapshotReceipt) -> RunArtifactSnapshotReceipt:
        self.calls += 1
        if self.fail:
            raise RunArtifactVerificationError("not finalized")
        return receipt


@dataclass(frozen=True)
class _Fixture:
    identity: RunIdentity
    manifest: object
    cycle: DecisionCycleIdentity
    checkpoint: RunCheckpointManifest


def _fixture() -> _Fixture:
    identity = RunIdentity("run-1", "session-1", "trace-1")
    manifest = frozen_runtime_manifest(experiment_spec_digest="study-1")
    cycle = DecisionCycleIdentity("run-1", "cycle-1", "session-1", "task-1", "trace-1")
    checkpoint = RunCheckpointManifest(
        checkpoint_id="checkpoint-1",
        schema_version="1",
        experiment_spec_digest="study-1",
        run_id="run-1",
        session_id="session-1",
        decision_cycle_id="cycle-1",
        cycle_identity_digest=cycle.digest(),
        participant_snapshots=(),
    )
    return _Fixture(identity, manifest, cycle, checkpoint)


def _target(fx: _Fixture, generation: int | None) -> RunControlTarget:
    return RunControlTarget(fx.identity.run_id, fx.manifest.digest(), generation)


def _controller(
    root: Path,
    fx: _Fixture,
    *,
    lifecycle: _Lifecycle | None = None,
    reconciliation: _Reconciliation | None = None,
    evidence: _Evidence | None = None,
    verifier: _Verifier | None = None,
    checkpoint: RunCheckpointManifest | None = None,
) -> DurableRunControl:
    actor = _InlineActor()
    ledger = DirectoryRunControlLedger(
        root,
        run_id=fx.identity.run_id,
        run_identity_digest=fx.identity.digest(),
        run_manifest_digest=fx.manifest.digest(),
        writer_actor=actor,
    )
    return DurableRunControl(
        identity=fx.identity,
        manifest=fx.manifest,
        ledger=ledger,
        lifecycle=lifecycle or _Lifecycle(),
        checkpoint_store=_CheckpointStore(checkpoint or fx.checkpoint),
        reconciliation=reconciliation or _Reconciliation(
            EffectReconciliationProof("reconcile-1", EffectReconciliationDisposition.NOT_APPLIED, None, {})
        ),
        evidence=evidence or _Evidence(),
        artifact_verifier=verifier or _Verifier(),
    )


def _evidence_receipt(fx: _Fixture, *, run_id: str = "run-1", manifest_digest: str | None = None) -> EvidenceBundleReceipt:
    bundle_id = "bundle-1"
    artifact = RunArtifactSnapshotReceipt(
        run_id=run_id,
        artifact_ref=f"evidence/{bundle_id}/manifest.json",
        artifact_kind=RunArtifactKind.EVIDENCE,
        generation="a" * 64,
        content_sha256="b" * 64,
        byte_size=10,
        record_count=None,
    )
    return EvidenceBundleReceipt(
        bundle_id=bundle_id,
        run_id=run_id,
        run_manifest_digest=manifest_digest or fx.manifest.digest(),
        manifest_artifact_receipt=artifact,
    )


def test_public_run_control_api_imports_without_loading_checkpoint_workload_cycle() -> None:
    from research_platform.experimentation.run.control.api import RunControlPort
    assert RunControlPort is not None


def test_run_inspect_restart_reconstructs_identical_authority(tmp_path: Path) -> None:
    fx = _fixture()
    first = _controller(tmp_path, fx)
    run = first.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    assert run.phase is RunControlPhase.RUNNING
    assert run.control_generation == 1

    restarted = _controller(tmp_path, fx)
    inspected = restarted.execute(RunControlRequest(RunControlAction.INSPECT, _target(fx, 1)))
    assert inspected.phase is RunControlPhase.RUNNING
    assert inspected.control_generation == 1
    assert inspected.control_event_receipt.event_digest == run.control_event_receipt.event_digest


def test_stale_generation_fails_before_lifecycle_side_effect(tmp_path: Path) -> None:
    fx = _fixture()
    lifecycle = _Lifecycle()
    control = _controller(tmp_path, fx, lifecycle=lifecycle)
    control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    with pytest.raises(RunControlStaleGeneration):
        control.execute(RunControlRequest(RunControlAction.STOP, _target(fx, 0)))
    assert lifecycle.stop_calls == 0


@pytest.mark.parametrize("mutation", ["truncated", "extra-field", "sequence-gap"])
def test_corrupt_control_ledger_fails_closed(tmp_path: Path, mutation: str) -> None:
    import json

    fx = _fixture()
    control = _controller(tmp_path, fx)
    control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    records = tmp_path / "control" / "records"
    first = records / "00000000000000000001.json"
    second = records / "00000000000000000002.json"
    if mutation == "truncated":
        second.write_bytes(second.read_bytes().rstrip(b"\n"))
    elif mutation == "extra-field":
        row = json.loads(second.read_text(encoding="utf-8"))
        row["unexpected"] = True
        second.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    else:
        second.rename(records / "00000000000000000003.json")
    assert first.is_file()
    with pytest.raises(RunControlIntegrityError):
        _controller(tmp_path, fx).execute(
            RunControlRequest(RunControlAction.INSPECT, _target(fx, None))
        )

def test_run_failure_is_durably_recovery_required_before_error_escapes(tmp_path: Path) -> None:
    fx = _fixture()
    control = _controller(tmp_path, fx, lifecycle=_Lifecycle(run_error=RuntimeError("open uncertain")))
    with pytest.raises(RunControlActionFailure) as raised:
        control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    assert raised.value.receipt.phase is RunControlPhase.RECOVERY_REQUIRED
    restarted = _controller(tmp_path, fx)
    inspected = restarted.execute(RunControlRequest(RunControlAction.INSPECT, _target(fx, 0)))
    assert inspected.phase is RunControlPhase.RECOVERY_REQUIRED
    assert inspected.control_generation == 0


def test_manifest_drift_is_rejected_before_state_access(tmp_path: Path) -> None:
    fx = _fixture()
    control = _controller(tmp_path, fx)
    with pytest.raises(RunControlConflict):
        control.execute(
            RunControlRequest(
                RunControlAction.RUN,
                RunControlTarget(fx.identity.run_id, "f" * 64, 0),
            )
        )
    assert not (tmp_path / "control" / "records").exists()


def test_resume_rejects_foreign_checkpoint_run_session(tmp_path: Path) -> None:
    fx = _fixture()
    control = _controller(tmp_path, fx)
    control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    control.execute(RunControlRequest(RunControlAction.STOP, _target(fx, 1)))
    foreign = RunCheckpointManifest(
        checkpoint_id="checkpoint-1",
        schema_version="1",
        experiment_spec_digest="study-1",
        run_id="run-other",
        session_id="session-other",
        decision_cycle_id="cycle-1",
        cycle_identity_digest=fx.cycle.digest(),
        participant_snapshots=(),
    )
    resumed = _controller(tmp_path, fx, checkpoint=foreign)
    with pytest.raises(RunControlIntegrityError, match="different run/session"):
        resumed.execute(
            RunControlRequest(
                RunControlAction.RESUME,
                _target(fx, 2),
                restore_checkpoint_id="checkpoint-1",
                restore_cycle_identity=fx.cycle,
            )
        )


def test_resume_binds_exact_checkpoint_and_restore_cycle_across_restart(tmp_path: Path) -> None:
    fx = _fixture()
    first = _controller(tmp_path, fx)
    first.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    first.execute(RunControlRequest(RunControlAction.STOP, _target(fx, 1)))
    restarted = _controller(tmp_path, fx)
    receipt = restarted.execute(
        RunControlRequest(
            RunControlAction.RESUME,
            _target(fx, 2),
            restore_checkpoint_id=fx.checkpoint.checkpoint_id,
            restore_cycle_identity=fx.cycle,
        )
    )
    assert receipt.phase is RunControlPhase.RUNNING
    assert receipt.control_generation == 3
    assert receipt.latest_checkpoint_id == fx.checkpoint.checkpoint_id
    assert receipt.checkpoint_manifest_digest == fx.checkpoint.digest()
    again = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 3))
    )
    assert again.latest_checkpoint_id == receipt.latest_checkpoint_id
    assert again.checkpoint_manifest_digest == receipt.checkpoint_manifest_digest


@pytest.mark.parametrize("proof", [
    EffectReconciliationProof("AUTO", EffectReconciliationDisposition.UNKNOWN, None, {}),
    EffectReconciliationProof(
        "AUTO",
        EffectReconciliationDisposition.APPLIED,
        EffectReceipt("effect-1", "d" * 64, EffectClass.RECONCILABLE, EffectCertainty.EFFECT_POSSIBLE),
        {},
    ),
])
def test_unknown_or_possible_reconciliation_never_reports_running(tmp_path: Path, proof) -> None:
    fx = _fixture()
    control = _controller(
        tmp_path,
        fx,
        lifecycle=_Lifecycle(run_phase=RunControlPhase.RECOVERY_REQUIRED),
        reconciliation=_Reconciliation(proof),
    )
    first = control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    assert first.phase is RunControlPhase.RECOVERY_REQUIRED
    receipt = control.execute(RunControlRequest(RunControlAction.RECONCILE, _target(fx, 0)))
    assert receipt.phase is RunControlPhase.RECOVERY_REQUIRED
    assert receipt.control_generation == 0


def test_confirmed_reconciliation_advances_recovery_to_running(tmp_path: Path) -> None:
    fx = _fixture()
    proof = EffectReconciliationProof(
        "AUTO",
        EffectReconciliationDisposition.APPLIED,
        EffectReceipt("effect-2", "e" * 64, EffectClass.RECONCILABLE, EffectCertainty.EFFECT_CONFIRMED),
        {},
    )
    control = _controller(
        tmp_path,
        fx,
        lifecycle=_Lifecycle(run_phase=RunControlPhase.RECOVERY_REQUIRED),
        reconciliation=_Reconciliation(proof),
    )
    control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    receipt = control.execute(RunControlRequest(RunControlAction.RECONCILE, _target(fx, 0)))
    assert receipt.phase is RunControlPhase.RUNNING
    assert receipt.control_generation == 1


def test_foreign_or_unfinalized_evidence_fails_closed(tmp_path: Path) -> None:
    fx = _fixture()
    base = _controller(tmp_path, fx)
    base.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))

    foreign = _controller(tmp_path, fx, evidence=_Evidence(_evidence_receipt(fx, run_id="run-other")))
    with pytest.raises(RunControlIntegrityError, match="different run/manifest"):
        foreign.execute(RunControlRequest(RunControlAction.EVIDENCE, _target(fx, 1)))

    unfinalized = _controller(
        tmp_path,
        fx,
        evidence=_Evidence(_evidence_receipt(fx)),
        verifier=_Verifier(fail=True),
    )
    with pytest.raises(RunControlIntegrityError, match="not finalized authority"):
        unfinalized.execute(RunControlRequest(RunControlAction.EVIDENCE, _target(fx, 1)))


def test_stop_resume_same_generation_has_one_fenced_winner(tmp_path: Path) -> None:
    fx = _fixture()
    initial = _controller(tmp_path, fx)
    initial.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))

    stop_lifecycle = _Lifecycle()
    resume_lifecycle = _Lifecycle()
    stopper = _controller(tmp_path, fx, lifecycle=stop_lifecycle)
    resumer = _controller(tmp_path, fx, lifecycle=resume_lifecycle)
    stopped = stopper.execute(RunControlRequest(RunControlAction.STOP, _target(fx, 1)))
    assert stopped.phase is RunControlPhase.STOPPED
    with pytest.raises(RunControlStaleGeneration):
        resumer.execute(
            RunControlRequest(
                RunControlAction.RESUME,
                _target(fx, 1),
                restore_checkpoint_id=fx.checkpoint.checkpoint_id,
                restore_cycle_identity=fx.cycle,
            )
        )
    assert resume_lifecycle.resume_calls == 0
    final = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 2))
    )
    assert final.phase is RunControlPhase.STOPPED
    assert final.control_generation == 2


def _process_control_action(root: str, action: str, start, output) -> None:
    fx = _fixture()
    lifecycle = _Lifecycle()
    control = _controller(Path(root), fx, lifecycle=lifecycle)
    start.wait(10)
    try:
        if action == "stop":
            receipt = control.execute(
                RunControlRequest(RunControlAction.STOP, _target(fx, 1))
            )
            calls = lifecycle.stop_calls
        else:
            receipt = control.execute(
                RunControlRequest(
                    RunControlAction.RESUME,
                    _target(fx, 1),
                    restore_checkpoint_id=fx.checkpoint.checkpoint_id,
                    restore_cycle_identity=fx.cycle,
                )
            )
            calls = lifecycle.resume_calls
        output.put((action, "ok", receipt.phase.value, receipt.control_generation, calls))
    except BaseException as exc:
        calls = lifecycle.stop_calls if action == "stop" else lifecycle.resume_calls
        output.put((action, "error", type(exc).__name__, None, calls))


def test_state_changing_actions_require_generation_fence() -> None:
    fx = _fixture()
    for action in (
        RunControlAction.RUN,
        RunControlAction.STOP,
        RunControlAction.RECONCILE,
    ):
        with pytest.raises(ValueError, match="requires expected_generation"):
            RunControlRequest(action, _target(fx, None))


def test_six_actions_survive_fresh_controller_instances(tmp_path: Path) -> None:
    fx = _fixture()
    run = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.RUN, _target(fx, 0))
    )
    assert (run.phase, run.control_generation) == (RunControlPhase.RUNNING, 1)

    inspect = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 1))
    )
    assert (inspect.phase, inspect.control_generation) == (RunControlPhase.RUNNING, 1)

    stop = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.STOP, _target(fx, 1))
    )
    assert (stop.phase, stop.control_generation) == (RunControlPhase.STOPPED, 2)

    resume = _controller(tmp_path, fx).execute(
        RunControlRequest(
            RunControlAction.RESUME,
            _target(fx, 2),
            restore_checkpoint_id=fx.checkpoint.checkpoint_id,
            restore_cycle_identity=fx.cycle,
        )
    )
    assert (resume.phase, resume.control_generation) == (RunControlPhase.RUNNING, 3)

    reconcile = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.RECONCILE, _target(fx, 3))
    )
    assert (reconcile.phase, reconcile.control_generation) == (RunControlPhase.RUNNING, 3)

    verifier = _Verifier()
    evidence = _controller(
        tmp_path,
        fx,
        evidence=_Evidence(_evidence_receipt(fx)),
        verifier=verifier,
    ).execute(RunControlRequest(RunControlAction.EVIDENCE, _target(fx, 3)))
    assert evidence.evidence_bundle_receipt is not None
    assert evidence.control_generation == 3
    assert verifier.calls == 1


def test_cross_process_same_generation_has_one_effectful_winner(tmp_path: Path) -> None:
    import multiprocessing

    fx = _fixture()
    initial = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.RUN, _target(fx, 0))
    )
    assert (initial.phase, initial.control_generation) == (RunControlPhase.RUNNING, 1)

    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    output = ctx.Queue()
    processes = [
        ctx.Process(target=_process_control_action, args=(str(tmp_path), "stop", start, output))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(20)
        assert process.exitcode == 0

    results = [output.get(timeout=5), output.get(timeout=5)]
    assert sum(row[4] for row in results) == 1, results
    assert all(row[1] in {"ok", "error"} for row in results)
    assert any(row[1] == "ok" for row in results)

    final = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 2))
    )
    assert final.control_generation == 2
    assert final.phase is RunControlPhase.STOPPED


def test_prepared_publication_failure_never_calls_lifecycle(tmp_path: Path, monkeypatch) -> None:
    from research_platform.experimentation.run.control.api import RunControlNotFound
    from research_platform.platform.kernel.durability import DurableFileWriteError
    import research_platform.experimentation.run.control.providers.directory_ledger as ledger_module

    fx = _fixture()
    lifecycle = _Lifecycle()
    real_publish = ledger_module.atomic_replace_bytes

    def fail_first_record(path, payload):
        if path.name == "00000000000000000001.json":
            raise DurableFileWriteError("injected prepare publication failure")
        return real_publish(path, payload)

    monkeypatch.setattr(ledger_module, "atomic_replace_bytes", fail_first_record)
    with pytest.raises(RunControlIntegrityError, match="failed before durable authority"):
        _controller(tmp_path, fx, lifecycle=lifecycle).execute(
            RunControlRequest(RunControlAction.RUN, _target(fx, 0))
        )
    assert lifecycle.run_calls == 0
    records = tmp_path / "control" / "records"
    assert not records.exists() or not tuple(records.glob("*.json"))

    monkeypatch.setattr(ledger_module, "atomic_replace_bytes", real_publish)
    with pytest.raises(RunControlNotFound):
        _controller(tmp_path, fx).execute(
            RunControlRequest(RunControlAction.INSPECT, _target(fx, None))
        )


def test_terminal_publication_failure_restarts_pending_without_reissuing_effect(tmp_path: Path, monkeypatch) -> None:
    from research_platform.platform.kernel.durability import DurableFileWriteError
    import research_platform.experimentation.run.control.providers.directory_ledger as ledger_module

    fx = _fixture()
    lifecycle = _Lifecycle()
    real_publish = ledger_module.atomic_replace_bytes

    def fail_terminal(path, payload):
        if path.name == "00000000000000000002.json":
            raise DurableFileWriteError("injected terminal publication failure")
        return real_publish(path, payload)

    monkeypatch.setattr(ledger_module, "atomic_replace_bytes", fail_terminal)
    with pytest.raises(RunControlActionFailure) as raised:
        _controller(tmp_path, fx, lifecycle=lifecycle).execute(
            RunControlRequest(RunControlAction.RUN, _target(fx, 0))
        )
    assert lifecycle.run_calls == 1
    assert raised.value.receipt.phase is RunControlPhase.RECOVERY_REQUIRED
    assert raised.value.receipt.control_generation == 0
    assert sorted(path.name for path in (tmp_path / "control" / "records").glob("*.json")) == [
        "00000000000000000001.json"
    ]

    replay_lifecycle = _Lifecycle()
    replay = _controller(tmp_path, fx, lifecycle=replay_lifecycle).execute(
        RunControlRequest(RunControlAction.RUN, _target(fx, 0))
    )
    assert replay.phase is RunControlPhase.RECOVERY_REQUIRED
    assert replay.control_generation == 0
    assert replay_lifecycle.run_calls == 0

    monkeypatch.setattr(ledger_module, "atomic_replace_bytes", real_publish)
    proof = EffectReconciliationProof(
        "AUTO",
        EffectReconciliationDisposition.APPLIED,
        EffectReceipt(
            "effect-run-1",
            "d" * 64,
            EffectClass.RECONCILABLE,
            EffectCertainty.EFFECT_CONFIRMED,
        ),
        {},
    )
    reconciled = _controller(
        tmp_path,
        fx,
        reconciliation=_Reconciliation(proof),
    ).execute(RunControlRequest(RunControlAction.RECONCILE, _target(fx, 0)))
    assert (reconciled.phase, reconciled.control_generation) == (RunControlPhase.RUNNING, 1)


def test_terminal_commit_crossing_atomic_replace_reconstructs_terminal_authority(tmp_path: Path, monkeypatch) -> None:
    from research_platform.platform.kernel.durability import DurableFileWriteError
    import research_platform.experimentation.run.control.providers.directory_ledger as ledger_module

    fx = _fixture()
    lifecycle = _Lifecycle()
    real_publish = ledger_module.atomic_replace_bytes

    def publish_then_signal_failure(path, payload):
        real_publish(path, payload)
        if path.name == "00000000000000000002.json":
            raise DurableFileWriteError("injected post-replace failure")

    monkeypatch.setattr(ledger_module, "atomic_replace_bytes", publish_then_signal_failure)
    receipt = _controller(tmp_path, fx, lifecycle=lifecycle).execute(
        RunControlRequest(RunControlAction.RUN, _target(fx, 0))
    )
    assert lifecycle.run_calls == 1
    assert (receipt.phase, receipt.control_generation) == (RunControlPhase.RUNNING, 1)
    restarted = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 1))
    )
    assert restarted.control_event_receipt.event_digest == receipt.control_event_receipt.event_digest


def test_initial_not_applied_reconciliation_records_failed_attempt_and_allows_new_run(tmp_path: Path) -> None:
    fx = _fixture()
    uncertain = _controller(
        tmp_path,
        fx,
        lifecycle=_Lifecycle(run_phase=RunControlPhase.RECOVERY_REQUIRED),
        reconciliation=_Reconciliation(
            EffectReconciliationProof(
                "AUTO",
                EffectReconciliationDisposition.NOT_APPLIED,
                EffectReceipt(
                    "effect-run-not-applied",
                    "a" * 64,
                    EffectClass.RECONCILABLE,
                    EffectCertainty.NO_EFFECT,
                ),
                {},
            )
        ),
    )
    pending = uncertain.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    assert (pending.phase, pending.control_generation) == (RunControlPhase.RECOVERY_REQUIRED, 0)
    failed = uncertain.execute(RunControlRequest(RunControlAction.RECONCILE, _target(fx, 0)))
    assert (failed.phase, failed.control_generation) == (RunControlPhase.FAILED, 1)

    lifecycle = _Lifecycle()
    retried = _controller(tmp_path, fx, lifecycle=lifecycle).execute(
        RunControlRequest(RunControlAction.RUN, _target(fx, 1))
    )
    assert lifecycle.run_calls == 1
    assert (retried.phase, retried.control_generation) == (RunControlPhase.RUNNING, 2)


def test_reconciliation_identity_mismatch_fails_closed_without_terminalizing(tmp_path: Path) -> None:
    fx = _fixture()
    control = _controller(
        tmp_path,
        fx,
        lifecycle=_Lifecycle(run_phase=RunControlPhase.RECOVERY_REQUIRED),
        reconciliation=_Reconciliation(
            EffectReconciliationProof(
                "wrong-operation",
                EffectReconciliationDisposition.APPLIED,
                EffectReceipt(
                    "effect-wrong",
                    "b" * 64,
                    EffectClass.RECONCILABLE,
                    EffectCertainty.EFFECT_CONFIRMED,
                ),
                {},
            )
        ),
    )
    control.execute(RunControlRequest(RunControlAction.RUN, _target(fx, 0)))
    with pytest.raises(RunControlIntegrityError, match="request_id does not match"):
        control.execute(RunControlRequest(RunControlAction.RECONCILE, _target(fx, 0)))
    inspected = _controller(tmp_path, fx).execute(
        RunControlRequest(RunControlAction.INSPECT, _target(fx, 0))
    )
    assert inspected.phase is RunControlPhase.RECOVERY_REQUIRED
    assert inspected.control_generation == 0
