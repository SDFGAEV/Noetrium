from __future__ import annotations

from pathlib import Path

from research_platform.governance.system_registry.api import system_catalog
from research_platform.governance.system_registry.api.contracts import STANDARD_SYSTEM_SHAPE

from .source_scan import SourceInvariantViolation, violation


def _standard_shape_packages(root: Path) -> tuple[tuple[Path, str], ...]:
    package_root = root / "research_platform"
    rows: list[tuple[Path, str]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_dir() or not (path / "__init__.py").is_file():
            continue
        relative = path.relative_to(package_root)
        # api/runtime/providers/composition are implementation planes, not systems.
        if any(part in STANDARD_SYSTEM_SHAPE for part in relative.parts):
            continue
        if not all(
            (path / plane).is_dir() and (path / plane / "__init__.py").is_file()
            for plane in STANDARD_SYSTEM_SHAPE
        ):
            continue
        module = "research_platform." + ".".join(relative.parts)
        rows.append((path, module))
    return tuple(rows)


def audit_system_topology_completeness(root: Path) -> list[SourceInvariantViolation]:
    """Fail closed on both undeclared concrete systems and stale package declarations.

    The catalog remains the sole topology declaration authority. Filesystem shape is
    discovery evidence only: a concrete standard-shaped package must have catalog
    ownership, while a catalog package authority must resolve to a real Python package.
    Non-package projections/facets must be represented outside this package-descriptor
    contract rather than leaving a missing package behind.
    """

    root = Path(root).resolve()
    descriptors = tuple(system_catalog())
    registered = {row.package_prefix for row in descriptors}
    rows: list[SourceInvariantViolation] = []
    canonical_catalog = root / "research_platform/governance/system_registry/catalog.json"
    if canonical_catalog.is_file():
        for descriptor in descriptors:
            package = root.joinpath(*descriptor.package_prefix.split("."))
            if (package / "__init__.py").is_file():
                continue
            rows.append(violation(
                root,
                canonical_catalog,
                "stale_catalog_package",
                1,
                (
                    f"catalog descriptor {descriptor.identity.key} declares package "
                    f"{descriptor.package_prefix} but that Python package is absent"
                ),
            ))
    for path, module in _standard_shape_packages(root):
        if module in registered:
            continue
        rows.append(violation(
            root,
            path / "__init__.py",
            "unregistered_standard_system",
            1,
            (
                f"standard system shape exists at {module} but no canonical "
                "system_registry/catalog.json descriptor owns it"
            ),
        ))
    return rows


__all__ = ["audit_system_topology_completeness"]
