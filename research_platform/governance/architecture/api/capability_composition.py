"""Public contracts for frozen, typed composition plans.

Projects and systems may depend on these values and the planner port. Concrete
validation remains in ``governance.architecture.runtime`` and is injected only
at a composition boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import inspect
import re
from typing import Protocol

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import ScopeIdentity


_TOKEN = re.compile(r"[a-z][a-z0-9_.-]*")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class CompositionContractError(ValueError):
    """A capability contract cannot be safely represented in a binding plan."""


class CompositionTopologyError(CompositionContractError):
    """A composition root attempts to compose a non-local subject."""


class CapabilityBindingError(CompositionContractError):
    """A requirement cannot be bound to an eligible provider."""


class MissingCapabilityProvider(CapabilityBindingError):
    pass


class AmbiguousCapabilityProvider(CapabilityBindingError):
    pass


class CapabilityInterfaceMismatch(CapabilityBindingError):
    pass


class CapabilityDependencyCycle(CapabilityBindingError):
    pass


class RequirementCardinality(StrEnum):
    EXACTLY_ONE = "exactly_one"
    ONE_OR_MORE = "one_or_more"


class CompositionSubjectKind(StrEnum):
    """Topology-governed system or independently composed project."""

    SYSTEM = "system"
    PROJECT = "project"


@dataclass(frozen=True, slots=True, order=True)
class CompositionSubject:
    """Owner/consumer identity without turning a project into a system node."""

    kind: CompositionSubjectKind
    subject_id: str
    system: SystemIdentity | None = None

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise CompositionContractError("composition subject_id must be non-empty")
        if self.kind is CompositionSubjectKind.SYSTEM:
            if self.system is None or self.subject_id != self.system.key:
                raise CompositionContractError(
                    "a system composition subject must carry its exact SystemIdentity"
                )
        elif self.system is not None:
            raise CompositionContractError("a project composition subject cannot carry SystemIdentity")

    @classmethod
    def system_subject(cls, identity: SystemIdentity) -> "CompositionSubject":
        return cls(CompositionSubjectKind.SYSTEM, identity.key, identity)

    @classmethod
    def project_subject(cls, project_id: str, version: str) -> "CompositionSubject":
        if not project_id.strip() or not version.strip():
            raise CompositionContractError("project composition identity requires id and version")
        return cls(CompositionSubjectKind.PROJECT, f"{project_id}@{version}")

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.subject_id}"


@dataclass(frozen=True, slots=True, order=True)
class CapabilityKey:
    """Stable public identity of one composition-time capability."""

    namespace: str
    name: str
    major_version: int

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.namespace):
            raise CompositionContractError("capability namespace must be a lowercase dotted token")
        if not _TOKEN.fullmatch(self.name):
            raise CompositionContractError("capability name must be a lowercase dotted token")
        if self.major_version <= 0:
            raise CompositionContractError("capability major_version must be positive")

    @property
    def value(self) -> str:
        return f"{self.namespace}.{self.name}.v{self.major_version}"


def _public_interface_members(base: type) -> dict[str, dict[str, str]]:
    """Materialize one MRO level; total work is linear in that level's members."""

    rows: dict[str, dict[str, str]] = {}
    for name, member in base.__dict__.items():
        if name.startswith("_"):
            continue
        if isinstance(member, property):
            getter = member.fget
            signature = str(inspect.signature(getter)) if getter is not None else ""
            rows[name] = {"name": name, "kind": "property", "signature": signature}
        elif callable(member):
            rows[name] = {
                "name": name,
                "kind": "callable",
                "signature": str(inspect.signature(member)),
            }
    return rows


def interface_contract_digest(interface: type) -> str:
    """Fingerprint the effective public callable/property surface of a port.

    Inherited members are part of the ABI. Walking the MRO from least to most
    specific preserves normal Python override semantics while preventing a
    parent Protocol signature change from leaving a child port digest stale.
    Runtime is O(N log N) for N total public members because each MRO level is
    visited once and only the final effective member names are sorted.
    """

    resolved: dict[str, dict[str, str]] = {}
    for base in reversed(interface.__mro__):
        if base is not object:
            resolved.update(_public_interface_members(base))
    members = tuple(resolved[name] for name in sorted(resolved))
    return canonical_digest(
        {"module": interface.__module__, "qualname": interface.__qualname__, "members": members}
    )


def _require_digest(value: str, field: str) -> None:
    if not _DIGEST.fullmatch(value):
        raise CompositionContractError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True, order=True)
class RequirementAddress:
    consumer: CompositionSubject
    requirement_id: str

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.requirement_id):
            raise CompositionContractError("requirement_id must be a lowercase dotted token")

    @property
    def value(self) -> str:
        return f"{self.consumer.key}:{self.requirement_id}"


@dataclass(frozen=True, slots=True)
class CapabilityOffer:
    """One provider candidate; it contains identity, never the provider object."""

    offer_id: str
    owner: CompositionSubject
    scope: ScopeIdentity
    capability: CapabilityKey
    interface_digest: str
    provider_identity: str
    configuration_digest: str
    exported_to_descendants: bool = True

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.offer_id):
            raise CompositionContractError("offer_id must be a lowercase dotted token")
        if not self.provider_identity.strip():
            raise CompositionContractError("provider_identity must be non-empty")
        _require_digest(self.interface_digest, "interface_digest")
        _require_digest(self.configuration_digest, "configuration_digest")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """One typed dependency declared by the consuming subject."""

    address: RequirementAddress
    scope: ScopeIdentity
    capability: CapabilityKey
    interface_digest: str
    cardinality: RequirementCardinality = RequirementCardinality.EXACTLY_ONE
    optional: bool = False

    def __post_init__(self) -> None:
        _require_digest(self.interface_digest, "interface_digest")


@dataclass(frozen=True, slots=True)
class CompositionContract:
    """All composition-facing offers and requirements of one local subject."""

    subject: CompositionSubject
    scope: ScopeIdentity
    offers: tuple[CapabilityOffer, ...] = ()
    requirements: tuple[CapabilityRequirement, ...] = ()

    def __post_init__(self) -> None:
        offer_ids = [offer.offer_id for offer in self.offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise CompositionContractError(f"duplicate offer id in {self.subject.key}")
        requirement_ids = [requirement.address.requirement_id for requirement in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise CompositionContractError(f"duplicate requirement id in {self.subject.key}")
        for offer in self.offers:
            if offer.owner != self.subject or offer.scope != self.scope:
                raise CompositionContractError("an offer must be owned at its contract subject and scope")
        for requirement in self.requirements:
            if requirement.address.consumer != self.subject or requirement.scope != self.scope:
                raise CompositionContractError(
                    "a requirement must be consumed at its contract subject and scope"
                )


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    """Explicit provider policy when a requirement has more than one candidate."""

    requirement: RequirementAddress
    offer_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.offer_ids:
            raise CompositionContractError("provider selection must name at least one offer")
        if len(self.offer_ids) != len(set(self.offer_ids)):
            raise CompositionContractError("provider selection contains a duplicate offer")


@dataclass(frozen=True, slots=True)
class CompositionIdentity:
    """Identity of one recursive composition root and its immutable scope."""

    composition_id: str
    scope: ScopeIdentity
    owner: CompositionSubject
    parent_plan_digest: str | None = None

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.composition_id):
            raise CompositionContractError("composition_id must be a lowercase dotted token")
        if self.parent_plan_digest is not None:
            _require_digest(self.parent_plan_digest, "parent_plan_digest")


@dataclass(frozen=True, slots=True)
class BindingEdge:
    requirement: RequirementAddress
    offer: CapabilityOffer


@dataclass(frozen=True, slots=True)
class BindingPlan:
    """Frozen, inspectable wiring evidence; it never stores runtime objects."""

    identity: CompositionIdentity
    contracts: tuple[CompositionContract, ...]
    imported_offers: tuple[CapabilityOffer, ...]
    edges: tuple[BindingEdge, ...]
    digest: str

    def bindings_for(self, requirement: RequirementAddress) -> tuple[BindingEdge, ...]:
        return tuple(edge for edge in self.edges if edge.requirement == requirement)


class CapabilityCompositionPlannerPort(Protocol):
    """Project-safe planner port injected by an outer composition boundary."""

    def freeze(
        self,
        identity: CompositionIdentity,
        contracts: tuple[CompositionContract, ...],
        *,
        imported_offers: tuple[CapabilityOffer, ...] = (),
        selections: tuple[ProviderSelection, ...] = (),
    ) -> BindingPlan: ...


__all__ = [
    "AmbiguousCapabilityProvider",
    "BindingEdge",
    "BindingPlan",
    "CapabilityBindingError",
    "CapabilityCompositionPlannerPort",
    "CapabilityDependencyCycle",
    "CapabilityInterfaceMismatch",
    "CapabilityKey",
    "CapabilityOffer",
    "CapabilityRequirement",
    "CompositionContract",
    "CompositionContractError",
    "CompositionIdentity",
    "CompositionSubject",
    "CompositionSubjectKind",
    "CompositionTopologyError",
    "MissingCapabilityProvider",
    "ProviderSelection",
    "RequirementAddress",
    "RequirementCardinality",
    "interface_contract_digest",
]
