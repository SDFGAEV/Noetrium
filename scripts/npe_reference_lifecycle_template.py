from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from noetrium.contracts.json import canonical_digest
from noetrium.contracts.research import (
    EvidenceBundleReceipt,
    RunArtifactKind,
    RunArtifactSnapshotReceipt,
    RunControlConflict,
    RunControlError,
    RunControlEventReceipt,
    RunControlIntegrityError,
    RunControlNotFound,
    RunControlPhase,
    RunControlRecordKind,
    RunControlReceipt,
    RunControlRequest,
    RunControlStaleGeneration,
    RunEvidenceValidity,
    RunExecutionOutcome,
    RunOutcomeProjection,
    RunScientificValidity,
    RunTaskOutcome,
)
from noetrium.platform import (
    ResearchAction,
    ResearchFacade,
    ResearchRequest,
    bind_run_control_application,
)

RUN_ID = "__RUN_ID__"
RUN_MANIFEST_DIGEST = "__RUN_MANIFEST_DIGEST__"
CHECKPOINT_ID = "checkpoint-1"
CYCLE = {
    "run_id": RUN_ID,
    "decision_cycle_id": "cycle-1",
    "session_id": "session-1",
    "task_id": "task-1",
    "trace_id": "trace-1",
}
STATE_KEYS = frozenset({
    "generation", "phase", "latest_checkpoint_id", "checkpoint_manifest_digest",
    "cycle_identity_digest", "event_sequence", "event_action", "operation_id",
    "event_digest", "evidence",
})


def _initial_state() -> dict[str, object]:
    return {
        "generation": 0,
        "phase": None,
        "latest_checkpoint_id": None,
        "checkpoint_manifest_digest": None,
        "cycle_identity_digest": canonical_digest(CYCLE),
        "event_sequence": 0,
        "event_action": None,
        "operation_id": None,
        "event_digest": None,
        "evidence": False,
    }


def _content_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checkpoint_digest() -> str:
    return canonical_digest({
        "run_id": RUN_ID,
        "checkpoint_id": CHECKPOINT_ID,
        "cycle_identity_digest": canonical_digest(CYCLE),
    })


def _load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return _initial_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or frozenset(data) != STATE_KEYS:
        raise RunControlIntegrityError("reference lifecycle state schema drifted")
    if type(data["generation"]) is not int or data["generation"] < 0:
        raise RunControlIntegrityError("reference lifecycle generation is invalid")
    if type(data["event_sequence"]) is not int or data["event_sequence"] < 0:
        raise RunControlIntegrityError("reference lifecycle event sequence is invalid")
    if type(data["evidence"]) is not bool:
        raise RunControlIntegrityError("reference lifecycle evidence flag is invalid")
    return data


def _write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".noetrium-state-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(state, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class ReferenceRunControl:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path

    @staticmethod
    def _operation_id(request: RunControlRequest, generation: int) -> str:
        return canonical_digest({
            "run_id": RUN_ID,
            "run_manifest_digest": RUN_MANIFEST_DIGEST,
            "action": request.action.value,
            "generation": generation,
            "restore_checkpoint_id": request.restore_checkpoint_id,
            "restore_cycle_identity_digest": (
                None if request.restore_cycle_identity is None
                else request.restore_cycle_identity.digest()
            ),
        })

    def _validate_target(self, request: RunControlRequest) -> None:
        target = request.target
        if target.run_id != RUN_ID or target.run_manifest_digest != RUN_MANIFEST_DIGEST:
            raise RunControlConflict("reference lifecycle target identity drifted")

    def _event(self, request: RunControlRequest, state: dict[str, object]) -> RunControlEventReceipt:
        phase = state["phase"]
        if not isinstance(phase, str):
            raise RunControlIntegrityError("reference lifecycle has no durable phase")
        generation = state["generation"]
        sequence = state["event_sequence"]
        if type(generation) is not int or type(sequence) is not int or sequence <= 0:
            raise RunControlIntegrityError("reference lifecycle durable event identity is invalid")
        operation_id = self._operation_id(request, generation)
        event_digest = canonical_digest({
            "run_id": RUN_ID,
            "record_sequence": sequence,
            "control_generation": generation,
            "action": request.action.value,
            "phase": phase,
            "operation_id": operation_id,
        })
        return RunControlEventReceipt(
            RUN_ID,
            sequence,
            RunControlRecordKind.TERMINAL,
            generation,
            request.action,
            RunControlPhase(phase),
            operation_id,
            event_digest,
        )

    def _evidence(self, state: dict[str, object]) -> EvidenceBundleReceipt | None:
        if state["evidence"] is not True:
            return None
        bundle_id = "npe-reference"
        artifact_ref = f"evidence/{bundle_id}/manifest.json"
        artifact_path = self._state_path.parent / artifact_ref
        raw = artifact_path.read_bytes()
        generation = canonical_digest({"run_id": RUN_ID, "generation": state["generation"]})
        artifact = RunArtifactSnapshotReceipt(
            RUN_ID,
            artifact_ref,
            RunArtifactKind.EVIDENCE,
            generation,
            _content_digest(raw),
            len(raw),
            None,
        )
        return EvidenceBundleReceipt(
            bundle_id,
            RUN_ID,
            RUN_MANIFEST_DIGEST,
            artifact,
        )

    def _receipt(self, request: RunControlRequest, state: dict[str, object]) -> RunControlReceipt:
        phase = RunControlPhase(state["phase"])
        execution = {
            RunControlPhase.RUNNING: RunExecutionOutcome.IN_PROGRESS,
            RunControlPhase.STOPPED: RunExecutionOutcome.STOPPED,
            RunControlPhase.RECOVERY_REQUIRED: RunExecutionOutcome.RECOVERY_REQUIRED,
            RunControlPhase.COMPLETED: RunExecutionOutcome.SUCCEEDED,
            RunControlPhase.FAILED: RunExecutionOutcome.FAILED,
        }[phase]
        evidence = self._evidence(state)
        return RunControlReceipt(
            request.action,
            RUN_ID,
            canonical_digest({"run_id": RUN_ID}),
            RUN_MANIFEST_DIGEST,
            phase,
            state["generation"],
            state["latest_checkpoint_id"],
            state["checkpoint_manifest_digest"],
            evidence,
            RunOutcomeProjection(
                execution,
                RunTaskOutcome.NOT_EVALUATED,
                RunEvidenceValidity.FINALIZED_VALID
                if evidence is not None
                else RunEvidenceValidity.NOT_FINALIZED
                if request.action.value == "evidence"
                else RunEvidenceValidity.NOT_OBSERVED,
                RunScientificValidity.NOT_EVALUATED,
            ),
            self._event(request, state),
        )

    def _commit(self, request: RunControlRequest, state: dict[str, object], phase: str) -> RunControlReceipt:
        generation = state["generation"]
        if type(generation) is not int:
            raise RunControlIntegrityError("reference lifecycle generation is invalid")
        state["generation"] = generation + 1
        state["phase"] = phase
        state["event_sequence"] = int(state["event_sequence"]) + 1
        state["event_action"] = request.action.value
        state["operation_id"] = self._operation_id(request, state["generation"])
        state["event_digest"] = canonical_digest({
            "run_id": RUN_ID,
            "sequence": state["event_sequence"],
            "generation": state["generation"],
            "action": request.action.value,
            "phase": phase,
            "operation_id": state["operation_id"],
        })
        _write_state(self._state_path, state)
        return self._receipt(request, state)

    def _require_generation(self, request: RunControlRequest, state: dict[str, object]) -> None:
        if request.target.expected_generation != state["generation"]:
            raise RunControlStaleGeneration("reference lifecycle expected generation is stale")

    def execute(self, request: RunControlRequest) -> RunControlReceipt:
        self._validate_target(request)
        state = _load_state(self._state_path)
        action = request.action.value
        if action in {"run", "stop", "resume", "reconcile"}:
            self._require_generation(request, state)
        if action == "inspect" or action == "reconcile":
            if state["phase"] is None:
                raise RunControlNotFound("reference lifecycle state does not exist")
            return self._receipt(request, state)
        if action == "run":
            if state["phase"] == "running":
                return self._receipt(request, state)
            if state["phase"] is not None:
                raise RunControlConflict("reference lifecycle cannot run from its current phase")
            state["latest_checkpoint_id"] = CHECKPOINT_ID
            state["checkpoint_manifest_digest"] = _checkpoint_digest()
            return self._commit(request, state, "running")
        if action == "stop":
            if state["phase"] != "running":
                raise RunControlConflict("reference lifecycle can stop only while running")
            return self._commit(request, state, "stopped")
        if action == "resume":
            cycle = request.restore_cycle_identity
            if state["phase"] != "stopped" or request.restore_checkpoint_id != CHECKPOINT_ID:
                raise RunControlConflict("reference lifecycle restore checkpoint is not current")
            if cycle is None or cycle.run_id != RUN_ID or cycle.session_id != CYCLE["session_id"]:
                raise RunControlIntegrityError("reference lifecycle restore cycle identity drifted")
            if cycle.decision_cycle_id != CYCLE["decision_cycle_id"] or cycle.task_id != CYCLE["task_id"]:
                raise RunControlIntegrityError("reference lifecycle restore cycle topology drifted")
            if cycle.trace_id != CYCLE["trace_id"] or cycle.digest() != canonical_digest(CYCLE):
                raise RunControlIntegrityError("reference lifecycle restore cycle digest drifted")
            if state["checkpoint_manifest_digest"] != _checkpoint_digest():
                raise RunControlIntegrityError("reference lifecycle checkpoint digest drifted")
            return self._commit(request, state, "running")
        if action == "evidence":
            if state["phase"] is None:
                raise RunControlNotFound("reference lifecycle state does not exist")
            if state["evidence"] is not True:
                bundle_id = "npe-reference"
                artifact_path = self._state_path.parent / "evidence" / bundle_id / "manifest.json"
                payload = {
                    "bundle_id": bundle_id,
                    "generation": state["generation"],
                    "run_id": RUN_ID,
                    "run_manifest_digest": RUN_MANIFEST_DIGEST,
                }
                raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                handle, temporary = tempfile.mkstemp(prefix=".noetrium-evidence-", dir=str(artifact_path.parent))
                try:
                    with os.fdopen(handle, "wb") as stream:
                        stream.write(raw)
                    os.replace(temporary, artifact_path)
                except BaseException:
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
                    raise
                state["evidence"] = True
            state["event_sequence"] = int(state["event_sequence"]) + 1
            state["event_action"] = action
            state["operation_id"] = self._operation_id(request, state["generation"])
            state["event_digest"] = canonical_digest({
                "run_id": RUN_ID,
                "sequence": state["event_sequence"],
                "generation": state["generation"],
                "action": action,
                "phase": state["phase"],
                "operation_id": state["operation_id"],
            })
            _write_state(self._state_path, state)
            return self._receipt(request, state)
        raise RunControlError("reference lifecycle action is unsupported")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 3:
        raise ValueError("reference lifecycle requires action, state path and JSON payload")
    action = ResearchAction(arguments[0])
    state_path = Path(arguments[1]).resolve()
    payload = json.loads(arguments[2])
    application = bind_run_control_application(
        ReferenceRunControl(state_path),
        run_id=RUN_ID,
        run_manifest_digest=RUN_MANIFEST_DIGEST,
    )
    facade = ResearchFacade(application)
    result = getattr(facade, action.value)(RUN_ID, payload)
    print(json.dumps({
        "ok": True,
        "action": result.action.value,
        "state": result.state,
        "payload": result.payload,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        print(json.dumps({
            "error": type(exc).__name__,
            "message": str(exc),
            "ok": False,
        }, sort_keys=True))
        raise SystemExit(1)
