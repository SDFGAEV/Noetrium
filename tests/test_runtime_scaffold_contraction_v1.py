from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RETIRED_PACKAGES = (
    "research_platform.reliability.diagnostics.causal",
    "research_platform.reliability.diagnostics.timeline",
    "research_platform.reliability.failure.catalog",
    "research_platform.reliability.failure.descriptor",
    "research_platform.reliability.failure.envelope",
    "research_platform.reliability.failure.fingerprint",
    "research_platform.reliability.failure.materialization",
    "research_platform.reliability.failure.taxonomy",
    "research_platform.reliability.incident",
    "research_platform.reliability.policy",
    "research_platform.reliability.reconciliation",
    "research_platform.reliability.recovery.evidence",
    "research_platform.reliability.recovery.plan",
    "research_platform.reliability.recovery.replay",
    "research_platform.resource.catalog",
)

RETIRED_PACKAGES += (
    "research_platform.runtime.control",
    "research_platform.runtime.history",
    "research_platform.runtime.process.identity",
    "research_platform.runtime.process.launch",
    "research_platform.runtime.process.lifecycle",
    "research_platform.runtime.session.binding",
    "research_platform.runtime.session.identity",
    "research_platform.runtime.supervision",
)

RETAINED_PARENT_SEAMS = (
    "research_platform/runtime/process/api/contracts.py",
    "research_platform/runtime/process/supervision/api/contracts.py",
    "research_platform/runtime/session/api/contracts.py",
    "research_platform/runtime/session/api/binding.py",
    "research_platform/runtime/session/runtime/binding.py",
    "research_platform/reliability/diagnostics/runtime/causal_graph.py",
    "research_platform/reliability/diagnostics/runtime/causal_projection.py",
    "research_platform/reliability/failure/api/contracts.py",
    "research_platform/reliability/failure/api/catalog.py",
    "research_platform/reliability/failure/api/fingerprint.py",
    "research_platform/reliability/effect/api/transitions.py",
    "research_platform/reliability/recovery/api/contracts.py",
    "research_platform/resource/compute/api/contracts.py",
    "research_platform/resource/lease/api/contracts.py",
)
def test_role02_generated_scaffold_packages_are_absent() -> None:
    for package in RETIRED_PACKAGES:
        path = ROOT.joinpath(*package.split("."))
        assert not any(path.rglob("*.py")), package
        assert not (path / "api" / "boundary.py").exists(), package


def test_role02_real_parent_authority_seams_remain() -> None:
    for relative in RETAINED_PARENT_SEAMS:
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        assert "SystemLeafContract" not in text, relative


def test_platform_source_does_not_import_retired_role02_shells() -> None:
    offenders: list[tuple[str, str]] = []
    retired = RETIRED_PACKAGES
    for path in (ROOT / "research_platform").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        for module in modules:
            if any(module == prefix or module.startswith(prefix + ".") for prefix in retired):
                offenders.append((path.relative_to(ROOT).as_posix(), module))
    assert offenders == []
