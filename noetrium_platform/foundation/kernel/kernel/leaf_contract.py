from __future__ import annotations

"""Neutral typed contract for generated platform leaf ownership seams."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from .json_value import JsonValue
from .canonical import canonical_bytes, canonical_digest, strict_json_loads
from .durability.durable_file import atomic_replace_bytes
from .errors import describe_exception
from .leaf_failure import LeafFailureClass, LeafFailureReceipt, receipt
from .logical_path import logical_absolute_path


class LeafExecutionError(RuntimeError):
    """A leaf cannot execute and carries a machine-diagnosable receipt."""
    def __init__(self, message: str, *, failure_receipt: LeafFailureReceipt | None = None):
        super().__init__(message)
        self.receipt = failure_receipt


@dataclass(frozen=True, slots=True)
class LeafStateSnapshot:
    generation: int
    values: Mapping[str, JsonValue]
    digest: str


class FileLeafStateStore:
    """Atomic, digest-bound state authority for one leaf runtime."""

    def __init__(self, path: str | Path) -> None:
        self.path = logical_absolute_path(path, expand_user=True)

    def read(self) -> LeafStateSnapshot:
        if not self.path.is_file():
            return LeafStateSnapshot(0, {}, canonical_digest({}))
        try:
            document = strict_json_loads(self.path.read_bytes())
            if not isinstance(document, dict):
                raise ValueError("leaf state root must be an object")
            generation = int(document["generation"])
            values = document["values"]
            digest = str(document["digest"])
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise LeafExecutionError(f"leaf state is unreadable: {self.path}") from exc
        if not isinstance(values, dict) or digest != canonical_digest(values):
            raise LeafExecutionError(f"leaf state integrity mismatch: {self.path}")
        return LeafStateSnapshot(generation, values, digest)

    def write(self, values: Mapping[str, JsonValue], *, expected_generation: int | None = None) -> LeafStateSnapshot:
        current = self.read()
        if expected_generation is not None and current.generation != expected_generation:
            raise LeafExecutionError("leaf state generation conflict")
        snapshot = LeafStateSnapshot(current.generation + 1, dict(values), canonical_digest(dict(values)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_bytes(
            {"generation": snapshot.generation, "values": snapshot.values, "digest": snapshot.digest}
        ) + b"\n"
        atomic_replace_bytes(self.path, payload)
        return snapshot


class LeafHandler(Protocol):
    def __call__(self, operation: str, payload: Mapping[str, JsonValue]) -> JsonValue: ...


@dataclass(frozen=True, slots=True)
class LeafExecutionResult:
    operation: str
    output: JsonValue
    contract_digest: str
    handler_id: str
    output_digest: str
    handler_bound: bool


@dataclass(frozen=True, slots=True)
class BoundSystemLeafRuntime:
    contract: "SystemLeafContract"
    handler: LeafHandler
    state_store: FileLeafStateStore | None = None

    @property
    def handler_id(self) -> str:
        handler_type = type(self.handler)
        return f"{handler_type.__module__}.{handler_type.__qualname__}"

    def execute(self, operation: str, payload: Mapping[str, JsonValue]) -> LeafExecutionResult:
        if not operation.strip():
            raise ValueError("leaf operation must be non-empty")
        if not isinstance(payload, Mapping):
            raise TypeError("leaf payload must be a mapping")
        try:
            output = self.handler(operation, payload)
        except LeafExecutionError:
            raise
        except (TimeoutError, ConnectionError) as exc:
            detail = describe_exception(exc).safe_message
            raise LeafExecutionError(detail, failure_receipt=receipt(exc, code="LEAF_EXTERNAL_UNCERTAIN", classification=LeafFailureClass.EXTERNAL_EFFECT_UNCERTAIN, retryable=False, effect_certainty="unknown", contract_digest=self.contract.digest)) from exc
        except (OSError, PermissionError) as exc:
            detail = describe_exception(exc).safe_message
            raise LeafExecutionError(detail, failure_receipt=receipt(exc, code="LEAF_PERSISTENCE_FAILURE", classification=LeafFailureClass.PERSISTENCE, retryable=True, effect_certainty="not_applicable", contract_digest=self.contract.digest)) from exc
        except (ValueError, TypeError, KeyError) as exc:
            detail = describe_exception(exc).safe_message
            raise LeafExecutionError(detail, failure_receipt=receipt(exc, code="LEAF_INVALID_INPUT", classification=LeafFailureClass.BUSINESS, retryable=False, effect_certainty="not_applied", contract_digest=self.contract.digest)) from exc
        except Exception as exc:
            detail = describe_exception(exc).safe_message
            raise LeafExecutionError(detail, failure_receipt=receipt(exc, code="LEAF_PROGRAMMING_FAILURE", classification=LeafFailureClass.PROGRAMMING, retryable=False, effect_certainty="unknown", contract_digest=self.contract.digest)) from exc
        return LeafExecutionResult(
            operation=operation,
            output=output,
            contract_digest=self.contract.digest,
            handler_id=self.handler_id,
            output_digest=canonical_digest(output),
            handler_bound=True,
        )

    def read_state(self) -> LeafStateSnapshot:
        if self.state_store is None:
            raise LeafExecutionError("leaf state store is not bound")
        return self.state_store.read()

    def checkpoint(self, values: Mapping[str, JsonValue], *, expected_generation: int | None = None) -> LeafStateSnapshot:
        if self.state_store is None:
            raise LeafExecutionError("leaf state store is not bound")
        return self.state_store.write(values, expected_generation=expected_generation)

    def restore(self, snapshot: LeafStateSnapshot) -> LeafStateSnapshot:
        return self.checkpoint(snapshot.values)


@dataclass(frozen=True, slots=True)
class SystemLeafContract:
    """Executable ownership contract for one catalog leaf."""

    system_id: str
    node: str
    package_prefix: str
    authority_id: str
    owns: str
    must_not_own: str
    api_module: str
    runtime_module: str
    provider_module: str
    composition_module: str

    def __post_init__(self) -> None:
        text_fields = (
            self.system_id, self.node, self.package_prefix, self.authority_id,
            self.owns, self.must_not_own, self.api_module, self.runtime_module,
            self.provider_module, self.composition_module,
        )
        if any(not value.strip() for value in text_fields):
            raise ValueError("system leaf contract fields must be non-empty")
        if not self.node.startswith(self.system_id + "/") and self.node != self.system_id:
            raise ValueError("system leaf node must be rooted at system_id")
        if not self.package_prefix.startswith("noetrium_platform."):
            raise ValueError("system leaf package must be inside noetrium_platform")
        expected = (
            ("api_module", self.package_prefix + ".api", self.api_module),
            ("runtime_module", self.package_prefix + ".runtime", self.runtime_module),
            ("provider_module", self.package_prefix + ".providers", self.provider_module),
            ("composition_module", self.package_prefix + ".composition", self.composition_module),
        )
        for field, expected_value, actual in expected:
            if actual != expected_value:
                raise ValueError(f"system leaf {field} drift")

    @property
    def digest(self) -> str:
        return canonical_digest(
            {
                "system_id": self.system_id,
                "node": self.node,
                "package_prefix": self.package_prefix,
                "authority_id": self.authority_id,
                "owns": self.owns,
                "must_not_own": self.must_not_own,
                "api_module": self.api_module,
                "runtime_module": self.runtime_module,
                "provider_module": self.provider_module,
                "composition_module": self.composition_module,
            }
        )


@dataclass(frozen=True, slots=True)
class SystemLeafRuntimeOwner:
    """Side-effect-free runtime owner bound to one leaf contract."""

    contract: SystemLeafContract

    def __post_init__(self) -> None:
        if not isinstance(self.contract, SystemLeafContract):
            raise TypeError("runtime owner requires a SystemLeafContract")

    @property
    def owner_id(self) -> str:
        return self.contract.authority_id

    def describe(self) -> dict[str, str]:
        return {
            "node": self.contract.node,
            "package_prefix": self.contract.package_prefix,
            "authority_id": self.contract.authority_id,
            "contract_digest": self.contract.digest,
        }

    def bind(self, handler: LeafHandler, state_path: str | Path | None = None) -> BoundSystemLeafRuntime:
        if not callable(handler):
            raise TypeError("leaf runtime handler must be callable")
        return BoundSystemLeafRuntime(self.contract, handler, FileLeafStateStore(state_path) if state_path is not None else None)


@dataclass(frozen=True, slots=True)
class SystemLeafProvider:
    """Provider seam: domain behavior must be injected at composition time."""

    contract: SystemLeafContract

    def describe(self) -> dict[str, str]:
        return {"provider_module": self.contract.provider_module, "contract_digest": self.contract.digest}

    def bind(self, handler: LeafHandler, state_path: str | Path | None = None) -> BoundSystemLeafRuntime:
        return SystemLeafRuntimeOwner(self.contract).bind(handler, state_path)


__all__ = [
    "BoundSystemLeafRuntime", "FileLeafStateStore", "LeafExecutionError", "LeafExecutionResult", "LeafFailureClass", "LeafFailureReceipt", "LeafStateSnapshot",
    "LeafHandler", "SystemLeafContract", "SystemLeafProvider", "SystemLeafRuntimeOwner",
]
