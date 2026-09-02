from __future__ import annotations

from pathlib import Path

from noetrium_platform.foundation.governance.system_registry.api import system_catalog

from .source_scan import SourceInvariantViolation, imports, violation


_CONCRETE_CHILDREN = ("runtime", "providers", "composition")


def audit_registered_public_facades(root: Path) -> list[SourceInvariantViolation]:
    """Registered system/subsystem roots may expose contracts, never concrete layers."""

    root = Path(root).resolve()
    rows: list[SourceInvariantViolation] = []
    for descriptor in system_catalog():
        package = root.joinpath(*descriptor.package_prefix.split("."))
        init = package / "__init__.py"
        if not init.is_file() or not (package / "api").is_dir():
            continue
        prefix = descriptor.package_prefix
        for module, line in imports(init):
            if any(
                module == f"{prefix}.{child}" or module.startswith(f"{prefix}.{child}.")
                for child in _CONCRETE_CHILDREN
            ):
                rows.append(
                    violation(
                        root,
                        init,
                        "registered_public_api_facade",
                        line,
                        (
                            f"registered boundary {descriptor.identity.key} re-exports concrete layer {module}; "
                            "root facades may expose API contracts only"
                        ),
                    )
                )
    return rows


__all__ = ["audit_registered_public_facades"]
