from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research_platform.operator.api import ResearchAction, ResearchRequest, ResearchResult
from research_platform.platform.kernel.durability import (
    InterprocessFileLock,
    atomic_replace_bytes,
    decode_checksummed_document,
    encode_checksummed_document,
)

_SCHEMA = "research-platform.operator-reference.v1"
_STATE_FIELDS = frozenset({"target", "phase", "generation", "events"})
_EVENT_FIELDS = frozenset({"sequence", "action", "phase", "generation"})
_EVENT_ACTIONS = frozenset({"run", "stop", "resume", "reconcile"})


def _positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _validate_reference_payload(payload: object, *, target: str) -> dict:
    if not isinstance(payload, dict) or set(payload) != _STATE_FIELDS:
        raise ValueError("reference state fields are invalid")
    if payload["target"] != target:
        raise ValueError("reference state target identity mismatch")
    if payload["phase"] not in {"running", "stopped"}:
        raise ValueError("reference state phase is invalid")
    generation = _positive_int(payload["generation"], field="reference state generation")
    events = payload["events"]
    if not isinstance(events, list) or not events:
        raise ValueError("reference state events are invalid")

    expected_phase = "running"
    expected_generation = 1
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict) or set(event) != _EVENT_FIELDS:
            raise ValueError("reference event fields are invalid")
        if _positive_int(event["sequence"], field="reference event sequence") != expected_sequence:
            raise ValueError("reference event sequence is not contiguous")
        action = event["action"]
        if not isinstance(action, str) or action not in _EVENT_ACTIONS:
            raise ValueError("reference event action is invalid")
        event_generation = _positive_int(event["generation"], field="reference event generation")
        if expected_sequence == 1:
            if action != "run":
                raise ValueError("reference event history must begin with run")
        elif action == "run":
            raise ValueError("reference event history contains duplicate run")
        elif action == "stop":
            if expected_phase != "running":
                raise ValueError("reference event stop transition is invalid")
            expected_phase = "stopped"
        elif action == "resume":
            if expected_phase != "stopped":
                raise ValueError("reference event resume transition is invalid")
            expected_phase = "running"
            expected_generation += 1
        if event["phase"] != expected_phase or event_generation != expected_generation:
            raise ValueError("reference event state transition is inconsistent")

    if payload["phase"] != expected_phase or generation != expected_generation:
        raise ValueError("reference state does not match event history")
    return payload


class ReferenceResearchApplication:
    """Durable deterministic lifecycle used only for product/conformance qualification."""

    def __init__(self, state_root: Path) -> None:
        self._root = Path(state_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, target: str) -> Path:
        digest = hashlib.sha256(target.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"

    def _lock_path(self, target: str) -> Path:
        return self._path(target).with_suffix(".lock")

    def _read(self, target: str) -> dict:
        path = self._path(target)
        if not path.is_file():
            raise FileNotFoundError(f"reference target does not exist: {target}")
        payload = decode_checksummed_document(
            path.read_bytes(), expected_schema=_SCHEMA
        ).payload
        return _validate_reference_payload(payload, target=target)

    def _write(self, target: str, payload: dict) -> None:
        validated = _validate_reference_payload(payload, target=target)
        atomic_replace_bytes(
            self._path(target),
            encode_checksummed_document(_SCHEMA, validated),
        )

    @staticmethod
    def _event(payload: dict, action: ResearchAction) -> dict:
        return {
            "sequence": len(payload["events"]) + 1,
            "action": action.value,
            "phase": payload["phase"],
            "generation": payload["generation"],
        }

    def _result(self, request: ResearchRequest, payload: dict) -> ResearchResult:
        if request.action is ResearchAction.EVIDENCE:
            result_payload = {
                "generation": payload["generation"],
                "events": tuple(payload["events"]),
            }
        else:
            result_payload = {
                "generation": payload["generation"],
                "event_count": len(payload["events"]),
            }
        return ResearchResult(
            request.action,
            request.target,
            payload["phase"],
            result_payload,
        )

    def _run(self, request: ResearchRequest) -> ResearchResult:
        path = self._path(request.target)
        if path.exists():
            raise ValueError(f"reference target already exists: {request.target}")
        payload = {
            "target": request.target,
            "phase": "running",
            "generation": 1,
            "events": [],
        }
        payload["events"].append(self._event(payload, ResearchAction.RUN))
        self._write(request.target, payload)
        return self._result(request, payload)

    def _stop(self, request: ResearchRequest, payload: dict) -> ResearchResult:
        if payload["phase"] != "running":
            raise ValueError("reference target is not running")
        payload["phase"] = "stopped"
        payload["events"].append(self._event(payload, ResearchAction.STOP))
        self._write(request.target, payload)
        return self._result(request, payload)

    def _resume(self, request: ResearchRequest, payload: dict) -> ResearchResult:
        if payload["phase"] != "stopped":
            raise ValueError("reference target is not stopped")
        payload["phase"] = "running"
        payload["generation"] += 1
        payload["events"].append(self._event(payload, ResearchAction.RESUME))
        self._write(request.target, payload)
        return self._result(request, payload)

    def _reconcile(self, request: ResearchRequest, payload: dict) -> ResearchResult:
        payload["events"].append(self._event(payload, ResearchAction.RECONCILE))
        self._write(request.target, payload)
        return self._result(request, payload)

    def execute(self, request: ResearchRequest) -> ResearchResult:
        if not isinstance(request, ResearchRequest):
            raise TypeError("reference application requires ResearchRequest")
        with InterprocessFileLock(self._lock_path(request.target)):
            if request.action is ResearchAction.RUN:
                return self._run(request)
            payload = self._read(request.target)
            if request.action is ResearchAction.INSPECT:
                return self._result(request, payload)
            if request.action is ResearchAction.STOP:
                return self._stop(request, payload)
            if request.action is ResearchAction.RESUME:
                return self._resume(request, payload)
            if request.action is ResearchAction.RECONCILE:
                return self._reconcile(request, payload)
            if request.action is ResearchAction.EVIDENCE:
                return self._result(request, payload)
            raise ValueError(f"unsupported research action: {request.action}")


def build_reference_application(config_path: Path | None) -> ReferenceResearchApplication:
    if config_path is None:
        raise ValueError("reference application requires --application-config")
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"state_root"}:
        raise ValueError("reference application config must contain only state_root")
    state_root = data["state_root"]
    if not isinstance(state_root, str) or not state_root.strip():
        raise ValueError("reference application state_root must be a non-empty string")
    return ReferenceResearchApplication(Path(state_root))


__all__ = ["ReferenceResearchApplication", "build_reference_application"]
