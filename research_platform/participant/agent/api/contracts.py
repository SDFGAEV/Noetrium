from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from research_platform.participant.capability.api import CapabilityPort
from research_platform.platform.kernel import ExecutionContext, JsonInput, JsonValue

from research_platform.participant._immutable_json import (
    freeze_json_input,
    freeze_json_value,
    freeze_json_value_object,
)


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str | None = None

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (self.agent_id, self.implementation_version, self.abi_version, self.schema_version)):
            raise ValueError("agent identity fields must be non-empty text")
        if self.artifact_digest is not None and (
            not isinstance(self.artifact_digest, str)
            or len(self.artifact_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.artifact_digest)
        ):
            raise ValueError("agent artifact_digest must be a lowercase SHA-256 digest when provided")


@dataclass(frozen=True, slots=True)
class AgentSnapshot:
    agent_id: str
    implementation_version: str
    schema_version: str
    session_id: str
    payload_sha256: str
    opaque_payload: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class AgentTurnRequest:
    task: JsonInput
    context: ExecutionContext
    input_payload: JsonInput | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, ExecutionContext):
            raise TypeError("agent turn context must be an ExecutionContext")
        object.__setattr__(self, "task", freeze_json_input(self.task, field="agent turn task"))
        if self.input_payload is not None:
            object.__setattr__(
                self, "input_payload", freeze_json_input(self.input_payload, field="agent turn input_payload")
            )


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    output: JsonValue
    agent_generation: str | None = None
    artifacts: tuple[str, ...] = ()
    diagnostics: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", freeze_json_value(self.output, field="agent turn output"))
        if self.agent_generation is not None and (
            not isinstance(self.agent_generation, str) or not self.agent_generation.strip()
        ):
            raise ValueError("agent_generation must be non-empty text when provided")
        if not isinstance(self.artifacts, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.artifacts
        ):
            raise TypeError("agent turn artifacts must be a tuple of non-empty strings")
        frozen_diagnostics = freeze_json_value_object(
            self.diagnostics, field="agent turn diagnostics"
        )
        object.__setattr__(self, "diagnostics", frozen_diagnostics)


@runtime_checkable
class AgentSession(Protocol):
    """Generic agent session that can only see an abstract capability port."""

    def run_turn(self, request: AgentTurnRequest, capabilities: CapabilityPort) -> AgentTurnResult: ...
    def checkpoint(self) -> AgentSnapshot: ...
    def restore(self, snapshot: AgentSnapshot) -> None: ...
    def diagnostics(self) -> Mapping[str, JsonValue]: ...
    def close(self) -> None: ...


@runtime_checkable
class AgentImplementation(Protocol):
    """Scientific/behavioral agent implementation with no session lifecycle authority."""
    @property
    def identity(self) -> AgentIdentity: ...
