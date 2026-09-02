from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentIdentity:
    component_id: str
    implementation_id: str
    implementation_version: str
    schema_version: str
    generation_id: str


@dataclass(frozen=True, slots=True)
class ImmutableModelIdentity:
    logical_name: str
    model_id: str
    revision: str
    engine: str
    engine_version: str
    dtype: str
    quantization: str | None
    context_length: int
    tokenizer_revision: str | None = None

    def resume_key(self) -> tuple[object, ...]:
        return (
            self.model_id,
            self.revision,
            self.engine,
            self.engine_version,
            self.dtype,
            self.quantization,
            self.context_length,
            self.tokenizer_revision,
        )
