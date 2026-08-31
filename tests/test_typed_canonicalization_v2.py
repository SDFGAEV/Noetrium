from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pytest

from research_platform.platform.kernel.canonical import (
    CanonicalEncodingError,
    canonical_digest,
    canonical_text,
)


class Kind(Enum):
    A = "a"


@dataclass
class Payload:
    name: str
    hidden: str = field(default="ignored", metadata={"transient": True})


def test_canonicalization_is_deterministic_for_supported_values() -> None:
    left = {"set": {3, 1, 2}, "tuple": (Kind.A, b"abc"), "record": Payload("x")}
    right = {"record": Payload("x"), "tuple": (Kind.A, b"abc"), "set": {2, 3, 1}}
    assert canonical_text(left) == canonical_text(right)
    assert canonical_digest(left) == canonical_digest(right)


def test_canonicalization_rejects_non_finite_float_and_non_string_keys() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalEncodingError):
            canonical_text(value)
    with pytest.raises(CanonicalEncodingError, match="string keys"):
        canonical_text({1: "x"})


def test_canonicalization_rejects_cycles_with_typed_error() -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(CanonicalEncodingError, match="cyclic"):
        canonical_text(cycle)


def test_canonicalization_enforces_explicit_depth_bound() -> None:
    value: object = "leaf"
    for _ in range(8):
        value = [value]
    with pytest.raises(CanonicalEncodingError, match="maximum depth"):
        canonical_text(value, max_depth=4)


def test_canonicalization_rejects_custom_objects() -> None:
    class Custom:
        pass

    with pytest.raises(CanonicalEncodingError, match="unsupported"):
        canonical_text(Custom())


def test_native_path_contract_is_not_claimed_portable() -> None:
    path = Path("root") / "child"
    assert canonical_text(path) == canonical_text(str(path))

def test_strict_json_decode_rejects_duplicates_nonfinite_and_bom() -> None:
    from research_platform.platform.kernel import CanonicalDecodingError, strict_json_loads

    assert strict_json_loads('{"a":[1,true,null]}') == {"a": [1, True, None]}
    with pytest.raises(CanonicalDecodingError, match="duplicate"):
        strict_json_loads('{"a":1,"a":2}')
    for token in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(CanonicalDecodingError, match="non-finite"):
            strict_json_loads('{"value":' + token + '}')
    with pytest.raises(CanonicalDecodingError, match="BOM"):
        strict_json_loads(b"\xef\xbb\xbf{}")


def test_frozen_json_is_deeply_immutable_and_alias_free() -> None:
    from collections.abc import Mapping
    from research_platform.platform.kernel import freeze_json, thaw_json

    source = {"nested": {"items": [1, {"value": 2}]}}
    frozen = freeze_json(source)
    assert isinstance(frozen, Mapping)
    source["nested"]["items"][1]["value"] = 99
    assert thaw_json(frozen) == {"nested": {"items": [1, {"value": 2}]}}
    with pytest.raises(TypeError):
        frozen["new"] = 1  # type: ignore[index]
    nested = frozen["nested"]
    assert isinstance(nested, Mapping)
    items = nested["items"]
    assert isinstance(items, tuple)
    with pytest.raises(TypeError):
        items[0] = 3  # type: ignore[index]


def test_frozen_json_rejects_cycles_nonfinite_and_non_string_keys() -> None:
    from research_platform.platform.kernel import CanonicalEncodingError, freeze_json

    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(CanonicalEncodingError, match="cyclic"):
        freeze_json(cycle)  # type: ignore[arg-type]
    with pytest.raises(CanonicalEncodingError, match="non-finite"):
        freeze_json({"x": float("nan")})
    with pytest.raises(CanonicalEncodingError, match="string keys"):
        freeze_json({1: "x"})  # type: ignore[dict-item]


def test_sha256_digest_requires_canonical_lowercase_text() -> None:
    from research_platform.platform.kernel import DigestValidationError, Sha256Digest, require_sha256

    value = "a" * 64
    assert require_sha256(value, "content_sha256") == value
    assert str(Sha256Digest(value)) == value
    for invalid in ("A" * 64, " a" * 32, "a" * 63, "g" * 64):
        with pytest.raises(DigestValidationError, match="canonical lowercase"):
            require_sha256(invalid, "content_sha256")


def test_kernel_canonical_bytes_match_existing_artifact_and_data_overlap() -> None:
    from research_platform.artifact._canonical import canonical_bytes as artifact_bytes
    from research_platform.data._canonical import canonical_bytes as data_bytes
    from research_platform.platform.kernel import canonical_bytes

    values = (
        None,
        True,
        7,
        1.25,
        "text",
        {"b": [3, 2, 1], "a": {"nested": False}},
        ("tuple", {"x": 1}),
    )
    for value in values:
        expected = canonical_bytes(value)
        assert artifact_bytes(value) == expected
        assert data_bytes(value) == expected

def test_strict_json_decode_rejects_values_outside_canonical_domain() -> None:
    from research_platform.platform.kernel import CanonicalDecodingError, strict_json_loads

    deep = '"leaf"'
    for _ in range(140):
        deep = '[' + deep + ']'
    with pytest.raises(CanonicalDecodingError, match="maximum depth"):
        strict_json_loads(deep)
    with pytest.raises(CanonicalDecodingError):
        strict_json_loads('"\\ud800"')

def test_role01_consumers_do_not_reimplement_kernel_json_or_sha_primitives() -> None:
    portfolio = Path(__file__).resolve().parents[1] / "research_platform/portfolio/api/contracts.py"
    leaf = Path(__file__).resolve().parents[1] / "research_platform/platform/kernel/leaf_contract.py"
    portfolio_source = portfolio.read_text(encoding="utf-8")
    leaf_source = leaf.read_text(encoding="utf-8")
    assert "_SHA256 =" not in portfolio_source
    assert "_reject_json_constant" not in portfolio_source
    assert "_unique_json_object" not in portfolio_source
    assert "json.loads(" not in portfolio_source
    assert "hashlib.sha256" not in leaf_source
    assert "json.dumps(" not in leaf_source
