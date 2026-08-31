from research_platform.governance.system_registry.api import system_catalog
from research_platform.governance.system_registry.runtime import InMemorySystemRegistry


TOP_LEVEL_SYSTEMS = {
    "platform", "scope", "portfolio", "experimentation", "execution", "participant",
    "resource", "environment", "model", "runtime", "data", "artifact",
    "reliability", "observability", "governance", "operator",
}


def _registry() -> InMemorySystemRegistry:
    registry = InMemorySystemRegistry()
    for descriptor in system_catalog():
        registry.register(descriptor)
    return registry


def test_complete_top_level_system_graph():
    rows = system_catalog()
    top_level = {row.identity.system_id for row in rows if row.identity.is_system}
    assert top_level == TOP_LEVEL_SYSTEMS
    assert all(row.parent_key is None for row in rows if row.identity.is_system)


def test_systems_are_peers_not_platform_children():
    registry = _registry()
    assert registry.children("platform")
    assert all(child.identity.system_id == "platform" for child in registry.children("platform"))
    assert "scope" not in {child.identity.key for child in registry.children("platform")}


def test_recursive_children_are_owned_by_their_system():
    registry = _registry()
    children = {child.identity.key for child in registry.children("observability/logging")}
    assert {
        "observability/logging/context",
        "observability/logging/record",
        "observability/logging/routing",
        "observability/logging/sink",
        "observability/logging/storage",
        "observability/logging/query",
        "observability/logging/projection",
        "observability/logging/retention",
        "observability/logging/capture",
    } <= children
