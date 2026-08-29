from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import math
from types import MappingProxyType
from typing import Protocol

from research_platform.platform.kernel import JsonInput, JsonValue


class ResearchAction(StrEnum):
    RUN = "run"
    INSPECT = "inspect"
    STOP = "stop"
    RESUME = "resume"
    RECONCILE = "reconcile"
    EVIDENCE = "evidence"


def _freeze_json(value: JsonInput, *, path: str = "payload") -> JsonValue:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} numbers must be finite JSON values")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            frozen[key] = _freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(item, path=f"{path}[{index}]") for index, item in enumerate(value))
    raise TypeError(f"{path} must contain JSON values")


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    action: ResearchAction
    target: str
    payload: JsonValue = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ResearchAction):
            raise TypeError("research action must be ResearchAction")
        if not isinstance(self.target, str):
            raise TypeError("research target must be a string")
        target = self.target.strip()
        if not target:
            raise ValueError("research target must not be blank")
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "payload", _freeze_json(self.payload))


@dataclass(frozen=True, slots=True)
class ResearchResult:
    action: ResearchAction
    target: str
    state: str
    payload: JsonValue = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ResearchAction):
            raise TypeError("research result action must be ResearchAction")
        if not isinstance(self.target, str) or not isinstance(self.state, str):
            raise TypeError("research result target/state must be strings")
        target = self.target.strip()
        state = self.state.strip()
        if not target or not state:
            raise ValueError("research result target/state must not be blank")
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "payload", _freeze_json(self.payload, path="result.payload"))


class ResearchApplicationPort(Protocol):
    """Application-owned authority behind the topology-hiding product facade."""

    def execute(self, request: ResearchRequest) -> ResearchResult: ...


class ResearchFacade:
    """Canonical Python facade; delegates every domain decision to an injected port."""

    def __init__(self, application: ResearchApplicationPort) -> None:
        if not callable(getattr(application, "execute", None)):
            raise TypeError("research application must implement execute(request)")
        self._application = application

    def _execute(
        self,
        action: ResearchAction,
        target: str,
        payload: JsonInput = None,
    ) -> ResearchResult:
        result = self._application.execute(ResearchRequest(action, target, payload))
        if not isinstance(result, ResearchResult):
            raise TypeError("research application returned a non-ResearchResult")
        if result.action is not action or result.target != target.strip():
            raise ValueError("research application result identity does not match request")
        return result

    def run(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.RUN, target, payload)

    def inspect(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.INSPECT, target, payload)

    def stop(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.STOP, target, payload)

    def resume(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.RESUME, target, payload)

    def reconcile(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.RECONCILE, target, payload)

    def evidence(self, target: str, payload: JsonInput = None) -> ResearchResult:
        return self._execute(ResearchAction.EVIDENCE, target, payload)


__all__ = [
    "ResearchAction",
    "ResearchApplicationPort",
    "ResearchFacade",
    "ResearchRequest",
    "ResearchResult",
]
