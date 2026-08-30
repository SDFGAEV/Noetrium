from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from research_platform.governance.repository_boundary import audit_downstream_project_imports
from research_platform.operator.api import ProjectCreateRequest, ProjectDoctorDisposition
from research_platform.operator.runtime import project_doctor, project_scaffold, project_testing
from research_platform.operator.runtime.project_platform_identity import InstalledPlatformIdentity
from research_platform.portfolio.api import (
    decode_project_manifest_bytes,
    encode_project_manifest,
    project_manifest_document,
)
_FIXED_PLATFORM = InstalledPlatformIdentity("0.1.0", "a" * 64)


def _bind_fixed_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        project_scaffold,
        "installed_platform_identity",
        lambda: _FIXED_PLATFORM,
    )
    monkeypatch.setattr(
        project_doctor,
        "installed_platform_identity",
        lambda: _FIXED_PLATFORM,
    )


def _checks(report) -> dict[str, ProjectDoctorDisposition]:
    return {row.check_id: row.disposition for row in report.checks}


def test_project_create_uses_canonical_manifest_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    request = ProjectCreateRequest("demo-project", "0.1.0", root, "standalone")

    first = project_scaffold.create_project(request)
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    second = project_scaffold.create_project(request)
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    manifest = decode_project_manifest_bytes((root / "project.manifest.json").read_bytes())
    assert manifest.project.identity.project_id == "demo-project"
    assert manifest.project.identity.version == "0.1.0"
    assert manifest.provenance.platform_artifact_sha256 == "a" * 64
    assert first.manifest_semantic_digest == project_manifest_document(manifest)["semantic_digest"]
    assert first == second
    assert before == after


def test_project_create_rejects_drift_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    request = ProjectCreateRequest("demo-project", "0.1.0", root)
    project_scaffold.create_project(request)
    readme = root / "README.md"
    readme.write_text("user change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="identical generated scaffold"):
        project_scaffold.create_project(request)

    assert readme.read_text(encoding="utf-8") == "user change\n"


def test_project_create_cleans_partial_publication_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    request = ProjectCreateRequest("demo-project", "0.1.0", root)
    original = project_scaffold.atomic_replace_bytes
    calls = 0

    def fail_publication(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected publication failure")
        original(path, payload)

    monkeypatch.setattr(project_scaffold, "atomic_replace_bytes", fail_publication)
    with pytest.raises(OSError, match="injected publication failure"):
        project_scaffold.create_project(request)

    assert not root.exists()


def test_project_create_rejects_incomplete_crash_residue_without_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    root.mkdir()
    partial = root / "README.md"
    partial.write_text("partial crash residue\n", encoding="utf-8")

    with pytest.raises(ValueError, match="identical generated scaffold"):
        project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))

    assert partial.read_text(encoding="utf-8") == "partial crash residue\n"
    assert not (root / ".research-platform-template").exists()


def test_project_doctor_rejects_manifest_and_private_import_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))

    initial = project_doctor.doctor_project(root)
    initial_checks = _checks(initial)
    assert initial_checks["project_manifest"] is ProjectDoctorDisposition.PASS
    assert initial_checks["manifest_identity"] is ProjectDoctorDisposition.PASS
    assert initial_checks["public_import_boundary"] is ProjectDoctorDisposition.PASS
    assert initial_checks["participant_provider_readiness"] is ProjectDoctorDisposition.BLOCKED
    assert initial_checks["model_provider_readiness"] is ProjectDoctorDisposition.BLOCKED
    assert initial_checks["environment_provider_readiness"] is ProjectDoctorDisposition.BLOCKED
    assert initial_checks["application_binding"] is ProjectDoctorDisposition.BLOCKED

    manifest_path = root / "project.manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
    private_source = root / "src" / "demo_project" / "private_import.py"
    private_source.write_text("from research_platform.operator.runtime import research_cli\n", encoding="utf-8")

    drifted = project_doctor.doctor_project(root)
    drifted_checks = _checks(drifted)
    assert drifted_checks["project_manifest"] is ProjectDoctorDisposition.BLOCKED
    assert drifted_checks["manifest_identity"] is ProjectDoctorDisposition.BLOCKED
    assert drifted_checks["public_import_boundary"] is ProjectDoctorDisposition.BLOCKED


def test_project_doctor_rejects_unknown_manifest_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))
    manifest_path = root / "project.manifest.json"
    manifest = decode_project_manifest_bytes(manifest_path.read_bytes())
    future = replace(manifest, template_revision="research-platform.project-template.v999")
    manifest_path.write_bytes(encode_project_manifest(future))

    report = project_doctor.doctor_project(root)
    checks = _checks(report)
    assert checks["project_manifest"] is ProjectDoctorDisposition.PASS
    assert checks["manifest_template_revision"] is ProjectDoctorDisposition.BLOCKED
    assert not report.ready


def test_project_create_normalizes_python_package_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    receipt = project_scaffold.create_project(
        ProjectCreateRequest("demo.project-alpha", "0.1.0", root)
    )
    assert "src/demo_project_alpha/project.py" in receipt.generated_files


def test_project_doctor_projects_typed_provider_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))

    report = project_doctor.doctor_project(root)
    rows = {row.check_id: row for row in report.checks}
    assert "PARTICIPANT_RUNTIME_UNAVAILABLE" in rows["participant_provider_readiness"].remediation
    assert "MODEL_QUALIFIED_BINDING_UNAVAILABLE" in rows["model_provider_readiness"].remediation
    assert "ENVIRONMENT_OPEN_NOTIMPLEMENTEDERROR" in rows["environment_provider_readiness"].remediation


def test_project_test_runs_generated_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))
    receipt = project_testing.test_project(root)
    assert receipt.passed

def test_generated_project_has_no_private_platform_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    project_scaffold.create_project(ProjectCreateRequest("demo-project", "0.1.0", root))

    report = audit_downstream_project_imports(root)
    assert report.passed, report.violations


def test_project_test_timeout_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "demo-project"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()

    def timeout(*args, **kwargs):
        del args, kwargs
        raise subprocess.TimeoutExpired(("python", "-m", "unittest"), 120)

    monkeypatch.setattr(project_testing.subprocess, "run", timeout)
    receipt = project_testing.test_project(root)
    assert receipt.exit_code == 124
    assert not receipt.passed


def test_project_cli_create_and_doctor_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import json
    from research_platform.operator.composition.research import main

    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "demo-project"
    assert main([
        "project", "create", "demo-project", str(root),
        "--version", "0.1.0", "--program-id", "standalone",
    ]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["ok"] is True
    assert created["result"]["manifest_semantic_digest"]

    assert main(["project", "doctor", "--project", str(root)]) == 4
    diagnosed = json.loads(capsys.readouterr().err)
    assert diagnosed["ok"] is False
    checks = {row["check_id"]: row["disposition"] for row in diagnosed["result"]["checks"]}
    assert checks["project_manifest"] == "pass"
    assert checks["participant_provider_readiness"] == "blocked"
    assert checks["model_provider_readiness"] == "blocked"
    assert checks["environment_provider_readiness"] == "blocked"
    assert checks["application_binding"] == "blocked"


def test_project_cli_loads_explicit_project_application_and_defaults_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import json
    from research_platform.operator.composition.research import main

    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "project-route"
    project_scaffold.create_project(ProjectCreateRequest("project-route", "0.1.0", root))
    application = root / "src" / "project_route" / "application.py"
    application.write_text(
        "from research_platform.api import ResearchResult\n\n"
        "class Application:\n"
        "    def execute(self, request):\n"
        "        return ResearchResult(request.action, request.target, 'accepted', {'route': 'project'})\n\n"
        "def build_application(config_path):\n"
        "    del config_path\n"
        "    return Application()\n",
        encoding="utf-8",
    )

    assert main(["run", "--project", str(root)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["result"]["target"] == "project-route"
    assert result["result"]["state"] == "accepted"
    assert result["result"]["payload"] == {"route": "project"}


def test_project_cli_rejects_ambiguous_application_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from research_platform.operator.composition.research import main

    _bind_fixed_platform(monkeypatch)
    root = tmp_path / "ambiguous-route"
    project_scaffold.create_project(ProjectCreateRequest("ambiguous-route", "0.1.0", root))
    exit_code = main([
        "--application", "example.module:factory",
        "run", "--project", str(root),
    ])
    assert exit_code == 2
    assert "either --project or --application" in capsys.readouterr().err
