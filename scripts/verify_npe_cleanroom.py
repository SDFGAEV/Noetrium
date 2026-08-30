from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    name: str
    argv: tuple[str, ...]
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True, slots=True)
class NpeCleanRoomReceipt:
    schema: str
    artifact_name: str
    artifact_sha256: str
    artifact_size: int
    installed_version: str | None
    module_file: str | None
    installed_import_isolated: bool
    template_revision: str | None
    project_created: bool
    doctor_ready: bool
    generated_tests_passed: bool
    public_import_boundary_passed: bool
    reference_lifecycle_complete: bool
    fresh_process_reopen_passed: bool
    npe_verified: bool
    blocker_codes: tuple[str, ...]
    commands: tuple[CommandReceipt, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _research_executable(root: Path) -> Path:
    return root / ("Scripts/research.exe" if os.name == "nt" else "bin/research")


def _receipt(name: str, argv: list[str], completed: subprocess.CompletedProcess[str]) -> CommandReceipt:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return CommandReceipt(
        name=name,
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout_sha256=_sha256_bytes(stdout.encode("utf-8")),
        stderr_sha256=_sha256_bytes(stderr.encode("utf-8")),
        stdout_tail=stdout[-4000:],
        stderr_tail=stderr[-4000:],
    )


def _run(name: str, argv: list[str], *, cwd: Path, env: dict[str, str]) -> CommandReceipt:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return _receipt(name, argv, completed)


def _json_output(receipt: CommandReceipt) -> dict[str, object] | None:
    raw = receipt.stdout_tail if receipt.returncode == 0 else receipt.stderr_tail
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _doctor_facts(receipt: CommandReceipt) -> tuple[bool, bool, str | None, tuple[str, ...]]:
    document = _json_output(receipt)
    if document is None:
        return False, False, None, ("DOCTOR_RECEIPT_INVALID",)
    result = document.get("result")
    if not isinstance(result, dict):
        return False, False, None, ("DOCTOR_RESULT_INVALID",)
    checks = result.get("checks")
    if not isinstance(checks, list):
        return False, False, None, ("DOCTOR_CHECKS_INVALID",)
    blocked: list[str] = []
    public_boundary = False
    for row in checks:
        if not isinstance(row, dict):
            return False, False, None, ("DOCTOR_CHECK_INVALID",)
        check_id = row.get("check_id")
        disposition = row.get("disposition")
        if isinstance(check_id, str) and disposition == "blocked":
            blocked.append(check_id)
        if check_id == "public_import_boundary":
            public_boundary = disposition == "pass"
    template = result.get("template_revision")
    return document.get("ok") is True, public_boundary, template if isinstance(template, str) else None, tuple(blocked)


def _blocked_receipt(
    artifact: Path,
    *,
    commands: list[CommandReceipt],
    blockers: list[str],
    installed_version: str | None = None,
    module_file: str | None = None,
    installed_import_isolated: bool = False,
    template_revision: str | None = None,
    project_created: bool = False,
    doctor_ready: bool = False,
    generated_tests_passed: bool = False,
    public_import_boundary_passed: bool = False,
) -> NpeCleanRoomReceipt:
    return NpeCleanRoomReceipt(
        schema="research-platform.npe-clean-room.v1",
        artifact_name=artifact.name,
        artifact_sha256=_sha256_file(artifact),
        artifact_size=artifact.stat().st_size,
        installed_version=installed_version,
        module_file=module_file,
        installed_import_isolated=installed_import_isolated,
        template_revision=template_revision,
        project_created=project_created,
        doctor_ready=doctor_ready,
        generated_tests_passed=generated_tests_passed,
        public_import_boundary_passed=public_import_boundary_passed,
        reference_lifecycle_complete=False,
        fresh_process_reopen_passed=False,
        npe_verified=False,
        blocker_codes=tuple(blockers),
        commands=tuple(commands),
    )


def verify_npe_cleanroom(artifact: Path) -> NpeCleanRoomReceipt:
    artifact = Path(artifact).resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    commands: list[CommandReceipt] = []
    blockers: list[str] = []
    with tempfile.TemporaryDirectory(prefix="research-npe-clean-room-") as td:
        root = Path(td)
        venv_root = root / "venv"
        work = root / "work"
        project = work / "npe-reference"
        work.mkdir()
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
        python = _venv_python(venv_root)
        research = _research_executable(venv_root)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"

        install = _run(
            "install-artifact",
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-deps", str(artifact)],
            cwd=work,
            env=env,
        )
        commands.append(install)
        if install.returncode != 0:
            return _blocked_receipt(artifact, commands=commands, blockers=["ARTIFACT_INSTALL_FAILED"])

        metadata_code = (
            "import importlib.metadata,json,research_platform.api;"
            "print(json.dumps({'version':importlib.metadata.version('research-platform'),"
            "'module_file':research_platform.api.__file__}))"
        )
        metadata = _run(
            "installed-metadata",
            [str(python), "-I", "-c", metadata_code],
            cwd=work,
            env=env,
        )
        commands.append(metadata)
        metadata_document = _json_output(metadata)
        installed_version = (
            metadata_document.get("version")
            if isinstance(metadata_document, dict) and isinstance(metadata_document.get("version"), str)
            else None
        )
        module_file = (
            metadata_document.get("module_file")
            if isinstance(metadata_document, dict) and isinstance(metadata_document.get("module_file"), str)
            else None
        )
        import_isolated = False
        if module_file is not None:
            try:
                module_path = Path(module_file).resolve()
                import_isolated = venv_root.resolve() in module_path.parents
            except OSError:
                import_isolated = False
        if metadata.returncode != 0 or installed_version is None or module_file is None:
            return _blocked_receipt(
                artifact,
                commands=commands,
                blockers=["INSTALLED_METADATA_INVALID"],
            )
        if not import_isolated:
            return _blocked_receipt(
                artifact,
                commands=commands,
                blockers=["INSTALLED_IMPORT_ESCAPED_VENV"],
                installed_version=installed_version,
                module_file=module_file,
            )

        profile_probe = _run(
            "reference-profile-probe",
            [str(research), "project", "create", "--help"],
            cwd=work,
            env=env,
        )
        commands.append(profile_probe)
        reference_profile = (
            profile_probe.returncode == 0
            and "--profile" in profile_probe.stdout_tail
            and "reference" in profile_probe.stdout_tail.lower()
        )

        create_argv = [
            str(research), "project", "create", "npe-reference", str(project),
            "--version", "0.0.1",
        ]
        if reference_profile:
            create_argv.extend(("--profile", "reference"))
        create = _run("project-create", create_argv, cwd=work, env=env)
        commands.append(create)
        create_document = _json_output(create)
        project_created = create.returncode == 0 and bool(
            isinstance(create_document, dict) and create_document.get("ok") is True
        )
        if not project_created:
            return _blocked_receipt(
                artifact,
                commands=commands,
                blockers=["PROJECT_CREATE_FAILED"],
                installed_version=installed_version,
                module_file=module_file,
                installed_import_isolated=True,
            )

        doctor = _run(
            "project-doctor",
            [str(research), "project", "doctor", "--project", str(project)],
            cwd=work,
            env=env,
        )
        commands.append(doctor)
        doctor_ready, public_boundary, template_revision, doctor_blockers = _doctor_facts(doctor)

        generated_tests = _run(
            "project-test",
            [str(research), "project", "test", "--project", str(project)],
            cwd=work,
            env=env,
        )
        commands.append(generated_tests)
        test_document = _json_output(generated_tests)
        tests_passed = generated_tests.returncode == 0 and bool(
            isinstance(test_document, dict) and test_document.get("ok") is True
        )

        if not reference_profile:
            blockers.append("REFERENCE_PROFILE_UNAVAILABLE")
        if not doctor_ready:
            blockers.extend(f"DOCTOR_BLOCKED:{check_id}" for check_id in doctor_blockers)
        if not tests_passed:
            blockers.append("GENERATED_TESTS_FAILED")
        if not public_boundary:
            blockers.append("PUBLIC_IMPORT_BOUNDARY_FAILED")
        if reference_profile and doctor_ready:
            blockers.append("REFERENCE_LIFECYCLE_DRIVER_UNAVAILABLE")

        return _blocked_receipt(
            artifact,
            commands=commands,
            blockers=blockers or ["NPE_ACCEPTANCE_INCOMPLETE"],
            installed_version=installed_version,
            module_file=module_file,
            installed_import_isolated=True,
            template_revision=template_revision,
            project_created=project_created,
            doctor_ready=doctor_ready,
            generated_tests_passed=tests_passed,
            public_import_boundary_passed=public_boundary,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Section-37 NPE from an installed artifact")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = verify_npe_cleanroom(args.artifact)
    except Exception as exc:
        print(f"NPE_CLEAN_ROOM_FAIL {type(exc).__qualname__}: {exc}", file=sys.stderr)
        return 1
    document = json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8", newline="\n")
    print(document, end="")
    return 0 if receipt.npe_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
