from __future__ import annotations

import hashlib
import json
from pathlib import Path

import scripts.verify_npe_cleanroom as npe


def _receipt(name: str, returncode: int, payload: dict | None = None, *, stdout: str | None = None) -> npe.CommandReceipt:
    text = stdout if stdout is not None else (json.dumps(payload) if payload is not None else "")
    if returncode == 0:
        stdout_tail, stderr_tail = text, ""
    else:
        stdout_tail, stderr_tail = "", text
    return npe.CommandReceipt(
        name=name,
        argv=(name,),
        returncode=returncode,
        stdout_sha256=hashlib.sha256(stdout_tail.encode()).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr_tail.encode()).hexdigest(),
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )


def _doctor(*, ready: bool, blocked: tuple[str, ...] = ()) -> dict:
    checks = [
        {"check_id": "public_import_boundary", "disposition": "pass", "summary": "public", "remediation": ""},
    ]
    for check_id in blocked:
        checks.append(
            {"check_id": check_id, "disposition": "blocked", "summary": "blocked", "remediation": "fix"}
        )
    return {
        "ok": ready,
        "command": "project doctor",
        "result": {
            "project_root": "project",
            "template_revision": "research-platform.project-template.v1",
            "checks": checks,
        },
    }


def test_doctor_facts_preserve_public_boundary_and_blocker_ids() -> None:
    receipt = _receipt(
        "project-doctor",
        4,
        _doctor(ready=False, blocked=("participant_provider_readiness", "application_binding")),
    )
    ready, public_boundary, template, blockers = npe._doctor_facts(receipt)
    assert ready is False
    assert public_boundary is True
    assert template == "research-platform.project-template.v1"
    assert blockers == ("participant_provider_readiness", "application_binding")


def test_doctor_facts_fail_closed_on_invalid_json() -> None:
    receipt = _receipt("project-doctor", 4, stdout="not-json")
    assert npe._doctor_facts(receipt) == (False, False, None, ("DOCTOR_RECEIPT_INVALID",))


def _bind_fake_venv(monkeypatch) -> dict[str, Path]:
    state: dict[str, Path] = {}
    def create(self, root):
        del self
        state["root"] = Path(root)
    monkeypatch.setattr(npe.venv.EnvBuilder, "create", create)
    return state


def test_clean_room_records_reference_profile_blocker_without_false_pass(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "research_platform.whl"
    artifact.write_bytes(b"wheel")
    venv_state = _bind_fake_venv(monkeypatch)

    rows = {
        "install-artifact": _receipt("install-artifact", 0),
        "reference-profile-probe": _receipt("reference-profile-probe", 0, stdout="usage: research project create PROJECT DEST"),
        "project-create": _receipt("project-create", 0, {"ok": True, "command": "project create", "result": {}}),
        "project-doctor": _receipt(
            "project-doctor",
            4,
            _doctor(ready=False, blocked=("participant_provider_readiness", "model_provider_readiness", "environment_provider_readiness", "application_binding")),
        ),
        "project-test": _receipt("project-test", 0, {"ok": True, "command": "project test", "result": {}}),
    }
    def fake_run(name, argv, cwd, env):
        del argv, cwd, env
        if name == "installed-metadata":
            module_file = venv_state["root"] / "Lib" / "site-packages" / "research_platform" / "api.py"
            return _receipt(name, 0, {"version": "0.43.1", "module_file": str(module_file)})
        return rows[name]
    monkeypatch.setattr(npe, "_run", fake_run)

    result = npe.verify_npe_cleanroom(artifact)
    assert result.npe_verified is False
    assert result.project_created is True
    assert result.generated_tests_passed is True
    assert result.public_import_boundary_passed is True
    assert result.reference_lifecycle_complete is False
    assert "REFERENCE_PROFILE_UNAVAILABLE" in result.blocker_codes
    assert "DOCTOR_BLOCKED:application_binding" in result.blocker_codes


def test_clean_room_does_not_claim_npe_when_reference_profile_exists_but_lifecycle_gate_is_unbound(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "research_platform.whl"
    artifact.write_bytes(b"wheel")
    venv_state = _bind_fake_venv(monkeypatch)
    rows = {
        "install-artifact": _receipt("install-artifact", 0),
        "reference-profile-probe": _receipt(
            "reference-profile-probe", 0, stdout="--profile {skeleton,reference}"
        ),
        "project-create": _receipt("project-create", 0, {"ok": True}),
        "project-doctor": _receipt("project-doctor", 0, _doctor(ready=True)),
        "project-test": _receipt("project-test", 0, {"ok": True}),
    }
    def fake_run(name, argv, cwd, env):
        del argv, cwd, env
        if name == "installed-metadata":
            module_file = venv_state["root"] / "Lib" / "site-packages" / "research_platform" / "api.py"
            return _receipt(name, 0, {"version": "0.43.1", "module_file": str(module_file)})
        return rows[name]
    monkeypatch.setattr(npe, "_run", fake_run)
    result = npe.verify_npe_cleanroom(artifact)
    assert result.doctor_ready is True
    assert result.npe_verified is False
    assert result.blocker_codes == ("REFERENCE_LIFECYCLE_DRIVER_UNAVAILABLE",)


def test_clean_room_rejects_installed_import_outside_verification_venv(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "research_platform.whl"
    artifact.write_bytes(b"wheel")
    _bind_fake_venv(monkeypatch)

    def fake_run(name, argv, cwd, env):
        del argv, cwd, env
        if name == "install-artifact":
            return _receipt(name, 0)
        if name == "installed-metadata":
            return _receipt(
                name,
                0,
                {"version": "0.43.1", "module_file": str(tmp_path / "checkout" / "research_platform" / "api.py")},
            )
        raise AssertionError(name)

    monkeypatch.setattr(npe, "_run", fake_run)
    result = npe.verify_npe_cleanroom(artifact)
    assert result.installed_import_isolated is False
    assert result.npe_verified is False
    assert result.blocker_codes == ("INSTALLED_IMPORT_ESCAPED_VENV",)
