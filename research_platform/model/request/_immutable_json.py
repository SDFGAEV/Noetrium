from __future__ import annotations

from collections.abc import Mapping
import math
from types import MappingProxyType
from typing import TypeAlias

from research_platform.platform.kernel import JsonInput, JsonObject, JsonValue


FrozenJsonValue: TypeAlias = JsonValue
FrozenJsonObject: TypeAlias = JsonObject
FrozenJsonArray: TypeAlias = tuple[JsonValue, ...]


def _freeze(value: JsonInput, *, field: str, active: set[int]) -> JsonValue:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field} contains a non-finite float")
        return value
    if not isinstance(value, (Mapping, list, tuple)):
        raise TypeError(f"{field} contains unsupported JSON value: {type(value).__name__}")

    identity = id(value)
    if identity in active:
        raise ValueError(f"{field} contains a recursive JSON container")
    active.add(identity)
    try:
        if isinstance(value, Mapping):
            rows: dict[str, JsonValue] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError(f"{field} requires string JSON object keys")
                rows[key] = _freeze(item, field=f"{field}.{key}", active=active)
            return MappingProxyType(rows)
        return tuple(
            _freeze(item, field=f"{field}[{index}]", active=active)
            for index, item in enumerate(value)
        )
    finally:
        active.remove(identity)


def freeze_json_value(value: JsonInput, *, field: str) -> FrozenJsonValue:
    return _freeze(value, field=field, active=set())


def freeze_json_object(value: Mapping[str, JsonInput], *, field: str) -> FrozenJsonObject:
    frozen = freeze_json_value(value, field=field)
    if not isinstance(frozen, Mapping):
        raise TypeError(f"{field} must be a JSON object")
    return frozen


__all__ = [
    "FrozenJsonArray",
    "FrozenJsonObject",
    "FrozenJsonValue",
    "freeze_json_object",
    "freeze_json_value",
]
