from __future__ import annotations

import pytest

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.governance.system_registry.runtime import build_default_system_registry
from research_platform.governance.architecture.api.capability_composition import (
    AmbiguousCapabilityProvider,
    CapabilityDependencyCycle,
    CapabilityInterfaceMismatch,
    CapabilityKey,
    CapabilityOffer,
    CapabilityRequirement,
    CompositionContract,
    CompositionIdentity,
    CompositionSubject,
    CompositionTopologyError,
    ProviderSelection,
    RequirementAddress,
    interface_contract_digest,
)
from research_platform.governance.architecture.runtime.capability_composition import (
    CapabilityCompositionPlanner,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.runtime.host.api import OperatingSystemRoute
from research_platform.runtime.server.identity.api import ServerConnectionFactoryPort
from research_platform.observability.logging.record.api import LoggingSystemPort
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind
from research_platform.scope.runtime import InMemoryScopeRegistry


HOST_ROUTE = CapabilityKey("runtime.host", "operating-system-route", 1)
SERVER_FACTORY = CapabilityKey("runtime.server", "connection-factory", 1)


def _scope_registry() -> InMemoryScopeRegistry:
    scopes = InMemoryScopeRegistry()
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "workspace")
    program = ScopeIdentity(ScopeKind.PROGRAM, "program")
    project = ScopeIdentity(ScopeKind.PROJECT, "project")
    scopes.register(workspace, PLATFORM_SCOPE)
    scopes.register(program, workspace)
    scopes.register(project, program)
    return scopes


def _offer(
    *,
    offer_id: str,
    owner: CompositionSubject,
    capability: CapabilityKey,
    interface: type,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    exported: bool = True,
) -> CapabilityOffer:
    return CapabilityOffer(
        offer_id=offer_id,
        owner=owner,
        scope=scope,
        capability=capability,
        interface_digest=interface_contract_digest(interface),
        provider_identity=f"{offer_id}.provider",
        configuration_digest=canonical_digest({"offer_id": offer_id, "scope": scope.key}),
        exported_to_descendants=exported,
    )


def _requirement(
    *,
    consumer: CompositionSubject,
    requirement_id: str,
    capability: CapabilityKey,
    interface: type,
    scope: ScopeIdentity = PLATFORM_SCOPE,
) -> CapabilityRequirement:
    return CapabilityRequirement(
        address=RequirementAddress(consumer, requirement_id),
        scope=scope,
        capability=capability,
        interface_digest=interface_contract_digest(interface),
    )


def _system(system_id: str, path: tuple[str, ...] = ()) -> CompositionSubject:
    return CompositionSubject.system_subject(SystemIdentity(system_id, path))


def test_plan_is_stable_metadata_and_never_a_runtime_container() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = _system("runtime", ("host",))
    server = _system("runtime", ("server",))
    offer = _offer(
        offer_id="local.host-route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    plan = planner.freeze(
        CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, _system("runtime")),
        (
            CompositionContract(host, PLATFORM_SCOPE, offers=(offer,)),
            CompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
        ),
    )

    assert plan.bindings_for(requirement.address)[0].offer == offer
    assert len(plan.digest) == 64
    assert not hasattr(plan, "resolve")
    assert not hasattr(plan, "get")


def test_ambiguous_provider_requires_explicit_selection() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = _system("runtime", ("host",))
    server = _system("runtime", ("server",))
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    contracts = (
        CompositionContract(
            host,
            PLATFORM_SCOPE,
            offers=(
                _offer(offer_id="host.a", owner=host, capability=HOST_ROUTE, interface=OperatingSystemRoute),
                _offer(offer_id="host.b", owner=host, capability=HOST_ROUTE, interface=OperatingSystemRoute),
            ),
        ),
        CompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    identity = CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, _system("runtime"))

    with pytest.raises(AmbiguousCapabilityProvider):
        planner.freeze(identity, contracts)

    plan = planner.freeze(
        identity,
        contracts,
        selections=(ProviderSelection(requirement.address, ("host.b",)),),
    )
    assert plan.bindings_for(requirement.address)[0].offer.offer_id == "host.b"


def test_incompatible_interface_digest_fails_before_binding() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = _system("runtime", ("host",))
    server = _system("runtime", ("server",))
    offer = _offer(
        offer_id="local.host-route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=ServerConnectionFactoryPort,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)

    with pytest.raises(CapabilityInterfaceMismatch):
        planner.freeze(
            CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, _system("runtime")),
            (
                CompositionContract(host, PLATFORM_SCOPE, offers=(offer,)),
                CompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
            ),
        )


def test_plan_rejects_cycles_and_nonlocal_child_composition() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = _system("runtime", ("host",))
    server = _system("runtime", ("server",))
    host_offer = _offer(
        offer_id="host.route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    server_offer = _offer(
        offer_id="server.factory",
        owner=server,
        capability=SERVER_FACTORY,
        interface=ServerConnectionFactoryPort,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    identity = CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, _system("runtime"))
    with pytest.raises(CapabilityDependencyCycle):
        planner.freeze(
            identity,
            (
                CompositionContract(
                    host,
                    PLATFORM_SCOPE,
                    offers=(host_offer,),
                    requirements=(
                        _requirement(
                            consumer=host,
                            requirement_id="server-factory",
                            capability=SERVER_FACTORY,
                            interface=ServerConnectionFactoryPort,
                        ),
                    ),
                ),
                CompositionContract(
                    server,
                    PLATFORM_SCOPE,
                    offers=(server_offer,),
                    requirements=(
                        _requirement(
                            consumer=server,
                            requirement_id="host-route",
                            capability=HOST_ROUTE,
                            interface=OperatingSystemRoute,
                        ),
                    ),
                ),
            ),
        )


def test_project_subject_binds_imported_system_offer_without_becoming_a_system_node() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    project_scope = ScopeIdentity(ScopeKind.PROJECT, "project")
    logging = _system("observability", ("logging",))
    project = CompositionSubject.project_subject("example-project", "1")
    logging_capability = CapabilityKey("observability.logging", "system", 1)
    logging_offer = _offer(
        offer_id="logging.platform-system",
        owner=logging,
        capability=logging_capability,
        interface=LoggingSystemPort,
    )
    requirement = _requirement(
        consumer=project,
        requirement_id="platform-logging",
        capability=logging_capability,
        interface=LoggingSystemPort,
        scope=project_scope,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    plan = planner.freeze(
        CompositionIdentity("project.example-project", project_scope, project),
        (CompositionContract(project, project_scope, requirements=(requirement,)),),
        imported_offers=(logging_offer,),
    )

    assert plan.bindings_for(requirement.address)[0].offer == logging_offer
    assert plan.contracts[0].subject == project
    assert plan.contracts[0].subject.kind.value == "project"
    assert not systems.contains("example-project")

    with pytest.raises(CompositionTopologyError):
        planner.freeze(
            CompositionIdentity("project.example-project", project_scope, project),
            (
                CompositionContract(project, project_scope),
                CompositionContract(_system("runtime", ("host",)), project_scope),
            ),
        )

    with pytest.raises(CompositionTopologyError):
        planner.freeze(
            CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, _system("runtime")),
            (
                CompositionContract(
                    _system("runtime", ("server", "identity")),
                    PLATFORM_SCOPE,
                ),
            ),
        )


def test_imported_offer_must_belong_to_a_registered_system() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    project_scope = ScopeIdentity(ScopeKind.PROJECT, "project")
    project = CompositionSubject.project_subject("example-project", "1")
    unregistered = _system("unregistered", ("logging",))
    imported = _offer(
        offer_id="unregistered.logging",
        owner=unregistered,
        capability=CapabilityKey("observability.logging", "system", 1),
        interface=LoggingSystemPort,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)

    with pytest.raises(CompositionTopologyError, match="not a registered system"):
        planner.freeze(
            CompositionIdentity("project.example-project", project_scope, project),
            (CompositionContract(project, project_scope),),
            imported_offers=(imported,),
        )


def test_large_plan_is_order_invariant_and_binds_by_capability() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = _system("runtime", ("host",))
    server = _system("runtime", ("server",))
    rows = []
    for index in range(128):
        capability = CapabilityKey("runtime.scale", f"cap-{index:03d}", 1)
        rows.append((
            _offer(
                offer_id=f"offer-{index:03d}",
                owner=host,
                capability=capability,
                interface=OperatingSystemRoute,
            ),
            _requirement(
                consumer=server,
                requirement_id=f"cap-{index:03d}",
                capability=capability,
                interface=OperatingSystemRoute,
            ),
        ))
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    identity = CompositionIdentity("runtime.scale-plan", PLATFORM_SCOPE, _system("runtime"))
    def freeze(items):
        return planner.freeze(
            identity,
            (
                CompositionContract(
                    host,
                    PLATFORM_SCOPE,
                    offers=tuple(item[0] for item in items),
                ),
                CompositionContract(
                    server,
                    PLATFORM_SCOPE,
                    requirements=tuple(item[1] for item in items),
                ),
            ),
        )

    forward = freeze(tuple(rows))
    reverse = freeze(tuple(reversed(rows)))
    assert forward.digest == reverse.digest
    assert forward.edges == reverse.edges
    assert len(forward.edges) == 128
    assert tuple(edge.offer.offer_id for edge in forward.edges) == tuple(
        f"offer-{index:03d}" for index in range(128)
    )


def test_interface_digest_tracks_inherited_port_surface() -> None:
    def accepts_int(self, value: int) -> str: ...
    def accepts_str(self, value: str) -> str: ...

    int_base = type("BasePort", (), {"operation": accepts_int})
    str_base = type("BasePort", (), {"operation": accepts_str})
    int_port = type("DerivedPort", (int_base,), {})
    str_port = type("DerivedPort", (str_base,), {})
    for port in (int_port, str_port):
        port.__module__ = "contract_probe"
        port.__qualname__ = "DerivedPort"

    assert interface_contract_digest(int_port) != interface_contract_digest(str_port)
