from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from research_platform.platform.kernel import ExecutionContext, JsonInput, canonical_digest


SurfaceT = TypeVar("SurfaceT")
TaskT = TypeVar("TaskT")
ResultT = TypeVar("ResultT")


@runtime_checkable
class ExperimentTrialProtocol(Protocol[SurfaceT, TaskT, ResultT]):
    protocol_id: str
    configuration_digest: str
    surface_id: str

    def run(
        self,
        surface: SurfaceT,
        context: ExecutionContext,
        *,
        task: TaskT,
        input_kind: str,
        input_payload: JsonInput,
    ) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class ExperimentTrialProtocolIdentity:
    protocol_id: str
    configuration_digest: str

    def __post_init__(self) -> None:
        if not self.protocol_id.strip():
            raise ValueError("protocol_id must be non-empty")
        if type(self.configuration_digest) is not str or len(self.configuration_digest) != 64 or any(ch not in "0123456789abcdef" for ch in self.configuration_digest):
            raise ValueError("configuration_digest must be lowercase SHA-256")

    def digest(self) -> str:
        return canonical_digest({"protocol_id": self.protocol_id, "configuration_digest": self.configuration_digest})


class ExperimentTrialProtocolIdentityMismatch(RuntimeError):
    pass


__all__ = [
    "ExperimentTrialProtocol",
    "ExperimentTrialProtocolIdentity",
    "ExperimentTrialProtocolIdentityMismatch",
]
