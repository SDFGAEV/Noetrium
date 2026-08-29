from __future__ import annotations

from collections.abc import Mapping
import math
from typing import TypeAlias

from research_platform.platform.kernel import JsonInput, JsonValue


FrozenJsonInput: TypeAlias = JsonInput
FrozenJsonValue: TypeAlias = JsonValue


class _ImmutableMixin:
    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> None:
        raise TypeError("frozen JSON value is immutable")


class FrozenJsonObject(_ImmutableMixin, dict[str, JsonInput]):
    """JSON object retaining normal mapping/serialization behavior without mutators."""

    def __init__(self, values: Mapping[str, JsonInput] | None = None) -> None:
        dict.__init__(self, {} if values is None else values)

    __setitem__ = _ImmutableMixin._immutable
    __delitem__ = _ImmutableMixin._immutable
    clear = _ImmutableMixin._immutable
    pop = _ImmutableMixin._immutable
    popitem = _ImmutableMixin._immutable
    setdefault = _ImmutableMixin._immutable
    update = _ImmutableMixin._immutable
    __ior__ = _ImmutableMixin._immutable

    def __copy__(self) -> "FrozenJsonObject":
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> "FrozenJsonObject":
        return self


class FrozenJsonArray(_ImmutableMixin, list[JsonInput]):
    """Request/input-side JSON array retaining list equality without mutators."""

    def __init__(self, values: list[JsonInput] | tuple[JsonInput, ...] = ()) -> None:
        list.__init__(self, values)

    __setitem__ = _ImmutableMixin._immutable
    __delitem__ = _ImmutableMixin._immutable
    __iadd__ = _ImmutableMixin._immutable
    __imul__ = _ImmutableMixin._immutable
    append = _ImmutableMixin._immutable
    clear = _ImmutableMixin._immutable
    extend = _ImmutableMixin._immutable
    insert = _ImmutableMixin._immutable
    pop = _ImmutableMixin._immutable
    remove = _ImmutableMixin._immutable
    reverse = _ImmutableMixin._immutable
    sort = _ImmutableMixin._immutable

    def __copy__(self) -> "FrozenJsonArray":
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> "FrozenJsonArray":
        return self


def _scalar(value: object, *, field: str) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field} contains a non-finite float")
        return value
    return NotImplemented


def freeze_json_input(value: JsonInput, *, field: str) -> FrozenJsonInput:
    scalar = _scalar(value, field=field)
    if scalar is not NotImplemented:
        return scalar  # type: ignore[return-value]
    if isinstance(value, Mapping):
        rows: dict[str, JsonInput] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{field} requires string JSON object keys")
            rows[key] = freeze_json_input(item, field=f"{field}.{key}")
        return FrozenJsonObject(rows)  # type: ignore[return-value]
    if isinstance(value, list):
        return FrozenJsonArray([
            freeze_json_input(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ])
    if isinstance(value, tuple):
        return tuple(
            freeze_json_input(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(f"{field} contains unsupported JSON value: {type(value).__name__}")


def freeze_json_value(value: JsonInput, *, field: str) -> FrozenJsonValue:
    scalar = _scalar(value, field=field)
    if scalar is not NotImplemented:
        return scalar  # type: ignore[return-value]
    if isinstance(value, Mapping):
        rows: dict[str, JsonInput] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{field} requires string JSON object keys")
            rows[key] = freeze_json_value(item, field=f"{field}.{key}")
        return FrozenJsonObject(rows)  # type: ignore[return-value]
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json_value(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(f"{field} contains unsupported JSON value: {type(value).__name__}")


def freeze_json_input_object(value: Mapping[str, JsonInput], *, field: str) -> FrozenJsonObject:
    frozen = freeze_json_input(value, field=field)
    if not isinstance(frozen, FrozenJsonObject):
        raise TypeError(f"{field} must be a JSON object")
    return frozen


def freeze_json_value_object(value: Mapping[str, JsonInput], *, field: str) -> FrozenJsonObject:
    frozen = freeze_json_value(value, field=field)
    if not isinstance(frozen, FrozenJsonObject):
        raise TypeError(f"{field} must be a JSON object")
    return frozen


__all__ = [
    "FrozenJsonArray", "FrozenJsonInput", "FrozenJsonObject", "FrozenJsonValue",
    "freeze_json_input", "freeze_json_input_object", "freeze_json_value", "freeze_json_value_object",
]
