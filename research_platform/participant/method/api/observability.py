from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from threading import RLock
from typing import Mapping, Protocol, runtime_checkable

from research_platform.platform.kernel import ExecutionContext, JsonValue
from research_platform.participant._immutable_json import freeze_json_value_object


def _method_observation_id(
    context: ExecutionContext, method_id: str, session_id: str, kind: str, payload: Mapping[str, JsonValue]
) -> str:
    document = {
        "context": asdict(context),
        "method_id": method_id,
        "session_id": session_id,
        "kind": kind,
        "payload": dict(payload),
    }
    raw = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return f"methodobs_{hashlib.sha256(raw).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class MethodObservation:
    observation_id: str
    context: ExecutionContext
    method_id: str
    session_id: str
    kind: str
    payload: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if not isinstance(self.context, ExecutionContext):
            raise TypeError("method observation context must be an ExecutionContext")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.method_id, self.session_id, self.kind)
        ):
            raise ValueError("method observation identity fields are required")
        frozen = freeze_json_value_object(self.payload, field="method observation payload")
        object.__setattr__(self, "payload", frozen)
        expected = _method_observation_id(
            self.context, self.method_id, self.session_id, self.kind, frozen
        )
        if self.observation_id != expected:
            raise ValueError("method observation identity does not match immutable payload")

    @classmethod
    def build(cls, context: ExecutionContext, method_id: str, session_id: str, kind: str, payload: Mapping[str, JsonValue]) -> "MethodObservation":
        frozen = freeze_json_value_object(payload, field="method observation payload")
        return cls(
            _method_observation_id(context, method_id, session_id, kind, frozen),
            context, method_id, session_id, kind, frozen,
        )


class MethodObservationDeliveryError(RuntimeError):
    def __init__(self, observation: MethodObservation, cause: BaseException) -> None:
        super().__init__(f"method observation delivery failed after scientific mutation commit: {observation.observation_id}: {cause}")
        self.observation = observation
        self.cause = cause
        self.mutation_committed = True
        self.recommended_recovery = "replay_observation"


@runtime_checkable
class MethodObservationSink(Protocol):
    def record(self, observation: MethodObservation) -> object: ...


@runtime_checkable
class MethodObservationOutboxPort(Protocol):
    """Method-facing durable handoff boundary for committed observations."""

    def restore(self, observations: tuple[MethodObservation, ...]) -> None: ...
    def snapshot(self) -> tuple[MethodObservation, ...]: ...
    def pending_count(self) -> int: ...
    def deliver(self, observation: MethodObservation) -> None: ...
    def flush(self) -> tuple[str, ...]: ...


@runtime_checkable
class MethodObservationOutboxFactoryPort(Protocol):
    """Creates an outbox without exposing the participant runtime implementation."""

    def create(self, sink: MethodObservationSink) -> MethodObservationOutboxPort: ...


@dataclass(frozen=True, slots=True)
class MethodServices:
    observation_sink: MethodObservationSink
