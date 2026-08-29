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
        if payload.get("target") != target:
            raise ValueError("reference state target identity mismatch")
        if payload.get("phase") not in {"running", "stopped"}:
            raise ValueError("reference state phase is invalid")
        if not isinstance(payload.get("generation"), int) or payload["generation"] < 1:
            raise ValueError("reference state generation is invalid")
        if not isinstance(payload.get("events"), list):
            raise ValueError("reference state events are invalid")
        return payload

    def _write(self, target: str, payload: dict) -> None:
        atomic_replace_bytes(
            self._path(target),
            encode_checksummed_document(_SCHEMA, payload),
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
