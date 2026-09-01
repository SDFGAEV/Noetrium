from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, is_transient_source_path, violation


def audit_observability_dependency_invariants(root: Path) -> list[SourceInvariantViolation]:
    api = root / "research_platform" / "observability" / "api"
    if not api.exists():
        return []
    rows: list[SourceInvariantViolation] = []
    forbidden = (
        "research_platform.reliability.forensics", "research_platform.observability.telemetry",
        "research_platform.operator",
    )
    for path in sorted(api.rglob("*.py")):
        for module, line in imports(path):
            if module.startswith(forbidden):
                rows.append(violation(root, path, "observability_api_backend_firewall", line, f"observability API imports concrete backend/control-plane module {module}"))
    return rows


def audit_observability_logging_leaf_invariants(root: Path) -> list[SourceInvariantViolation]:
    """Require logging ownership to remain in the registered leaf nodes."""
    rows: list[SourceInvariantViolation] = []
    logging_root = root / "research_platform" / "observability" / "logging"
    # Release/evidence tests also audit isolated temporary source fixtures.  A
    # fixture that does not contain this subsystem cannot violate its ownership
    # contract and must not be forced to materialize the whole platform tree.
    if not logging_root.exists():
        return rows
    legacy_import_prefixes = (
        "research_platform.observability.logging.api",
        "research_platform.observability.logging.runtime",
    )
    scan_roots = (
        root / "research_platform",
        root / "projects",
    )
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if is_transient_source_path(path):
                continue
            for module, line in imports(path):
                if any(module == prefix or module.startswith(prefix + ".") for prefix in legacy_import_prefixes):
                    rows.append(violation(
                        root,
                        path,
                        "logging_leaf_import_authority",
                        line,
                        f"logging caller imports retired parent implementation seam {module}; use the registered leaf node interface",
                    ))

    retired = (
        root / "research_platform" / "observability" / "logging" / "api" / "contracts.py",
        root / "research_platform" / "observability" / "logging" / "api" / "ports.py",
        root / "research_platform" / "observability" / "logging" / "runtime" / "logger.py",
        root / "research_platform" / "observability" / "logging" / "runtime" / "sinks.py",
    )
    for path in retired:
        if path.exists():
            rows.append(violation(
                root,
                path,
                "logging_legacy_ownership",
                1,
                "retired parent logging implementation remains after leaf migration",
            ))

    required = (
        "observability/logging/context/api/contracts.py",
        "observability/logging/record/api/contracts.py",
        "observability/logging/sink/api/ports.py",
        "observability/logging/query/api/ports.py",
        "observability/logging/record/runtime/logger.py",
        "observability/logging/routing/runtime/fanout.py",
        "observability/logging/storage/runtime/in_memory.py",
    )
    for relative in required:
        path = root / "research_platform" / relative
        if not path.exists():
            rows.append(violation(
                root,
                path,
                "logging_leaf_ownership_missing",
                1,
                "registered logging leaf has no concrete interface or implementation",
            ))
    return rows


__all__ = [
    "audit_observability_dependency_invariants",
    "audit_observability_logging_leaf_invariants",
]
