from __future__ import annotations

from collections.abc import Mapping
import math
from typing import TypeAlias

from research_platform.platform.kernel import JsonInput


FrozenJsonValue: TypeAlias = JsonInput


class _ImmutableMixin:
    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> None:
        raise TypeError("frozen JSON value is immutable")


class FrozenJsonObject(_ImmutableMixin, dict[str, FrozenJsonValue]):
    """JSON-serializable mapping that rejects mutation after construction."""

    def __init__(self, values: Mapping[str, FrozenJsonValue] | None = None) -> None:
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


class FrozenJsonArray(_ImmutableMixin, list[FrozenJsonValue]):
    """JSON-serializable array with standard list equality and no mutation."""

    def __init__(self, values: list[FrozenJsonValue] | tuple[FrozenJsonValue, ...] = ()) -> None:
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


def freeze_json_value(value: JsonInput, *, field: str) -> FrozenJsonValue:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        rows: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{field} requires string JSON object keys")
            rows[key] = freeze_json_value(item, field=f"{field}.{key}")
        return FrozenJsonObject(rows)
    if isinstance(value, (list, tuple)):
        return FrozenJsonArray([
            freeze_json_value(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ])
    raise TypeError(f"{field} contains unsupported JSON value: {type(value).__name__}")


def freeze_json_object(value: Mapping[str, JsonInput], *, field: str) -> FrozenJsonObject:
    frozen = freeze_json_value(value, field=field)
    if not isinstance(frozen, FrozenJsonObject):
        raise TypeError(f"{field} must be a JSON object")
    return frozen


__all__ = [
    "FrozenJsonArray", "FrozenJsonObject", "FrozenJsonValue",
    "freeze_json_object", "freeze_json_value",
]
