from __future__ import annotations
from typing import Protocol, runtime_checkable
from .contracts import SystemSpec

@runtime_checkable
class SystemPort(Protocol):
    @property
    def spec(self) -> SystemSpec: ...
