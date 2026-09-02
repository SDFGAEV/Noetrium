from __future__ import annotations
from ..api import SystemSpec, SystemPort

class SystemService(SystemPort):
    """Framework-only boundary; business behavior is supplied by child systems/providers."""
    def __init__(self, spec: SystemSpec) -> None:
        self._spec = spec
    @property
    def spec(self) -> SystemSpec:
        return self._spec
