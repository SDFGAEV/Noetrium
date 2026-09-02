from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RetentionClass(StrEnum):
    HOT_DEBUG = "hot_debug"
    RUN_DURABLE = "run_durable"
    SCIENTIFIC_DURABLE = "scientific_durable"


@dataclass(frozen=True, slots=True)
class RawObservationSchema:
    family: str
    schema_version: str
    required_fields: tuple[str, ...]
    retention: RetentionClass
    description: str

    def __post_init__(self) -> None:
        if not self.family.strip() or not self.schema_version.strip():
            raise ValueError("raw observation family and schema_version must be non-empty")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("raw observation required_fields must be unique")
        if any(not field.strip() for field in self.required_fields):
            raise ValueError("raw observation required_fields must be non-empty")


@dataclass(frozen=True, slots=True)
class RawObservationReceipt:
    family: str
    schema_version: str
    run_id: str
    segment_path: str
    sequence: int
    record_sha256: str
    bytes_written: int

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.family, self.schema_version, self.run_id, self.segment_path)):
            raise ValueError("raw observation receipt identity fields must be non-empty")
        if self.sequence <= 0 or self.bytes_written <= 0:
            raise ValueError("raw observation receipt sequence and bytes_written must be positive")
        if len(self.record_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.record_sha256):
            raise ValueError("raw observation receipt record_sha256 must be lowercase SHA-256")


class RawObservationCorruptionError(RuntimeError):
    pass
