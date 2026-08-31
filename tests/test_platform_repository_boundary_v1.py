from __future__ import annotations

import json
from pathlib import Path

from research_platform.governance.repository_boundary import (
    DownstreamImportKind,
    audit_downstream_project_imports,
    audit_repository_boundary,
)


def _minimal_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "research_platform" / "governance" / "system_registry").mkdir(parents=True)
    (root / "research_platform" / "core").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "research_platform" / "core" / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "research_platform" / "governance" / "system_registry" / "catalog.json").write_text(
        json.dumps({"governance": {"package_prefix": "research_platform.governance"}}), encoding="utf-8"
    )
    (root / "pyproject.toml").write_text('[tool.setuptools.packages.find]\ninclude = ["research_platform*"]\n', encoding="utf-8")
    (root / "deploy" / "Dockerfile").write_text("COPY research_platform ./research_platform\n", encoding="utf-8")
    return root


def test_clean_upstream_repository_passes(tmp_path: Path) -> None:
    report = audit_repository_boundary(_minimal_root(tmp_path))
    assert report.passed
    assert report.violations == ()


def test_downstream_directory_and_core_import_fail_closed(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "projects" / "demo").mkdir(parents=True)
    (root / "research_platform" / "core" / "bad.py").write_text("from projects.demo import app\n", encoding="utf-8")
    report = audit_repository_boundary(root)
    codes = {row.code for row in report.violations}
    assert "DOWNSTREAM_PATH_IN_UPSTREAM" in codes
    assert "CORE_IMPORTS_DOWNSTREAM" in codes


def test_packaging_and_image_cannot_embed_downstream(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "pyproject.toml").write_text('include = ["research_platform*", "projects*"]\n', encoding="utf-8")
    (root / "deploy" / "Dockerfile").write_text("COPY projects ./projects\n", encoding="utf-8")
    codes = {row.code for row in audit_repository_boundary(root).violations}
    assert "PACKAGE_INCLUDES_DOWNSTREAM" in codes
    assert "IMAGE_COPIES_DOWNSTREAM" in codes


def test_release_manifest_cannot_publish_downstream_paths(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "RELEASE_MANIFEST.json").write_text(
        json.dumps({"files": [{"path": "projects/demo/app.py"}]}), encoding="utf-8"
    )
    report = audit_repository_boundary(root)
    assert any(row.code == "RELEASE_INCLUDES_DOWNSTREAM" for row in report.violations)


def test_bundled_minecraft_environment_is_upstream_owned(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "research_platform" / "environment" / "minecraft").mkdir(parents=True)
    catalog = root / "research_platform" / "governance" / "system_registry" / "catalog.json"
    catalog.write_text(json.dumps({"environment/minecraft": {"package_prefix": "research_platform.environment.minecraft"}}), encoding="utf-8")
    (root / "RELEASE_MANIFEST.json").write_text(
        json.dumps({"files": [{"path": "research_platform/environment/minecraft/api/contracts.py"}]}), encoding="utf-8"
    )
    report = audit_repository_boundary(root)
    assert report.passed, report.violations


def test_unapproved_environment_provider_fails_closed(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "research_platform" / "environment" / "demo_world").mkdir(parents=True)
    catalog = root / "research_platform" / "governance" / "system_registry" / "catalog.json"
    catalog.write_text(json.dumps({"environment/demo_world": {"package_prefix": "research_platform.environment.demo_world"}}), encoding="utf-8")
    codes = {row.code for row in audit_repository_boundary(root).violations}
    assert "CONCRETE_ENVIRONMENT_IN_UPSTREAM" in codes
    assert "REGISTRY_OWNS_DOWNSTREAM_ENVIRONMENT" in codes


def test_current_repository_boundary_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    report = audit_repository_boundary(root, include_release_manifest=False)
    assert report.passed, report.violations

def test_minimal_downstream_project_imports_public_contracts_without_becoming_platform_source(tmp_path: Path) -> None:
    root = tmp_path / "downstream"
    package = root / "src" / "example_project"
    package.mkdir(parents=True)
    (package / "app.py").write_text(
        "from research_platform.portfolio.api import ProjectManifest\n"
        "from research_platform.operator.api import ResearchApplicationPort\n",
        encoding="utf-8",
    )
    (package / "provider.py").write_text(
        "from research_platform.environment.catalog.api import EnvironmentSpec\n",
        encoding="utf-8",
    )
    report = audit_downstream_project_imports(root)
    assert report.passed, report.violations
    observed = {(row.module, row.kind) for row in report.observations}
    assert ("research_platform.portfolio.api", DownstreamImportKind.COMMON_PLATFORM_API) in observed
    assert ("research_platform.operator.api", DownstreamImportKind.COMMON_PLATFORM_API) in observed
    assert (
        "research_platform.environment.catalog.api",
        DownstreamImportKind.PROVIDER_DEVELOPMENT_API,
    ) in observed
    assert not (root / "research_platform").exists()


def test_downstream_project_private_platform_import_and_vendoring_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "downstream"
    package = root / "src" / "example_project"
    package.mkdir(parents=True)
    (package / "bad.py").write_text(
        "from research_platform.runtime.process.runtime import ProcessRuntime\n",
        encoding="utf-8",
    )
    (root / "research_platform").mkdir()
    report = audit_downstream_project_imports(root)
    codes = {row.code for row in report.violations}
    assert "DOWNSTREAM_PRIVATE_PLATFORM_IMPORT" in codes
    assert "DOWNSTREAM_VENDORS_PLATFORM" in codes
    private = next(row for row in report.observations if row.module.startswith("research_platform.runtime"))
    assert private.kind is DownstreamImportKind.FORBIDDEN_PRIVATE_IMPLEMENTATION


def test_downstream_project_source_parse_failure_is_blocking(tmp_path: Path) -> None:
    root = tmp_path / "downstream"
    root.mkdir()
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    report = audit_downstream_project_imports(root)
    assert not report.passed
    assert {row.code for row in report.violations} == {"DOWNSTREAM_SOURCE_PARSE_FAILED"}
