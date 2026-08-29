from __future__ import annotations

import ast
from pathlib import Path

from research_platform.governance.system_registry.api import system_catalog

from .source_index import source_tree
from .source_scan import SourceInvariantViolation, violation


_CONTRACT_FIELDS = (
    "system_id",
    "node",
    "package_prefix",
    "authority_id",
    "owns",
    "must_not_own",
    "api_module",
    "runtime_module",
    "provider_module",
    "composition_module",
)


def _system_leaf_contract(tree: ast.AST) -> tuple[int, dict[str, str]] | None:
    """Return one literal SystemLeafContract declaration from an API boundary."""

    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        fn = item.func
        if not (isinstance(fn, ast.Name) and fn.id == "SystemLeafContract"):
            continue
        values: dict[str, str] = {}
        by_name = {keyword.arg: keyword.value for keyword in item.keywords if keyword.arg}
        for field in _CONTRACT_FIELDS:
            raw = by_name.get(field)
            if not isinstance(raw, ast.Constant) or not isinstance(raw.value, str):
                continue
            values[field] = raw.value
        return item.lineno, values
    return None


def _expected_contract(descriptor) -> dict[str, str]:
    package = descriptor.package_prefix
    return {
        "system_id": descriptor.identity.system_id,
        "node": descriptor.identity.key,
        "package_prefix": package,
        "authority_id": descriptor.authority_id or "",
        "owns": descriptor.owns,
        "must_not_own": descriptor.must_not_own,
        "api_module": package + ".api",
        "runtime_module": package + ".runtime",
        "provider_module": package + ".providers",
        "composition_module": package + ".composition",
    }


def audit_catalog_contract_consistency(root: Path) -> list[SourceInvariantViolation]:
    """Bind declared leaf contracts to the canonical registry without importing them.

    Algorithm-Complexity: O(N)
    Algorithm-Rationale: N is the number of registered descriptors plus AST nodes in
    API boundaries that already declare SystemLeafContract; every descriptor and AST
    is visited at most once and comparisons are over a fixed field set.
    """

    root = Path(root).resolve()
    rows: list[SourceInvariantViolation] = []
    for descriptor in system_catalog():
        boundary = root.joinpath(*descriptor.package_prefix.split("."), "api", "boundary.py")
        if not boundary.is_file():
            continue
        declared = _system_leaf_contract(source_tree(boundary))
        if declared is None:
            continue
        line, actual = declared
        expected = _expected_contract(descriptor)
        missing = tuple(field for field in _CONTRACT_FIELDS if field not in actual)
        if missing:
            rows.append(violation(
                root,
                boundary,
                "leaf_contract_metadata_nonliteral",
                line,
                "SystemLeafContract metadata must be literal for registry verification: "
                + ", ".join(missing),
            ))
            continue
        for field in _CONTRACT_FIELDS:
            if actual[field] == expected[field]:
                continue
            rows.append(violation(
                root,
                boundary,
                "leaf_contract_catalog_drift",
                line,
                (
                    f"{descriptor.identity.key} {field} drift: catalog={expected[field]!r} "
                    f"leaf_contract={actual[field]!r}"
                ),
            ))
    return rows


__all__ = ["audit_catalog_contract_consistency"]
