from __future__ import annotations

import json

from research_platform.platform.kernel import canonical_bytes, canonical_digest, canonical_text


class DataCanonicalDecodingError(ValueError):
    pass


def _reject_constant(token: str) -> object:
    raise DataCanonicalDecodingError(
        f"data canonical JSON forbids non-finite constant: {token}"
    )


def _object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DataCanonicalDecodingError(
                f"data canonical JSON contains duplicate object key: {key!r}"
            )
        result[key] = value
    return result


def strict_json_loads(raw: str | bytes) -> object:
    try:
        return json.loads(
            raw,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_from_pairs,
        )
    except DataCanonicalDecodingError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataCanonicalDecodingError("data canonical JSON cannot be decoded") from exc


__all__ = [
    "DataCanonicalDecodingError",
    "canonical_bytes",
    "canonical_digest",
    "canonical_text",
    "strict_json_loads",
]
