from __future__ import annotations

from noetrium_platform.foundation.governance.system_registry.api import system_catalog

from .registry import InMemorySystemRegistry


def build_default_system_registry() -> InMemorySystemRegistry:
    registry = InMemorySystemRegistry()
    for descriptor in system_catalog():
        registry.register(descriptor)
    return registry


__all__ = ["build_default_system_registry"]
