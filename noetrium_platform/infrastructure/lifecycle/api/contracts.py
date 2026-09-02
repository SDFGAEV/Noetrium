from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SystemIdentity:
    id: str
    version: str = "1"
    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("system id must be non-empty")
        if not self.version.strip():
            raise ValueError("system version must be non-empty")

@dataclass(frozen=True, slots=True)
class SystemSpec:
    identity: SystemIdentity
    purpose: str
    children: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("system purpose must be non-empty")
