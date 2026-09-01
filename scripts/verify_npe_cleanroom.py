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


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    name: str
    argv: tuple[str, ...]
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str
    stderr_tail: str
    json_output: str | None


@dataclass(frozen=True, slots=True)
class NpeCleanRoomReceipt:
    schema: str
    artifact_name: str
    artifact_sha256: str
    artifact_size: int
    installed_version: str | None
    module_file: str | None
    installed_import_isolated: bool
    template_profile: str | None
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

def _create_venv(root: Path) -> bool:
    try:
        import venv
    except ModuleNotFoundError:
        return False
    venv.EnvBuilder(with_pip=True, clear=True).create(root)
    return True



def _reject_json_constant(token: str) -> object:
    raise ValueError(f"non-finite JSON constant: {token}")


def _strict_json_object(raw: str) -> dict[str, object] | None:
    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw, parse_constant=_reject_json_constant, object_pairs_hook=object_from_pairs
        )
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _receipt(name: str, argv: list[str], completed: subprocess.CompletedProcess[str]) -> CommandReceipt:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    selected = stdout if completed.returncode == 0 else stderr
    return CommandReceipt(
        name=name,
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout_sha256=_sha256_bytes(stdout.encode("utf-8")),
        stderr_sha256=_sha256_bytes(stderr.encode("utf-8")),
        stdout_tail=stdout[-4000:],
        stderr_tail=stderr[-4000:],
        json_output=(
            selected if _strict_json_object(selected) is not None else None
        ),
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
    if receipt.json_output is None:
        return None
    return _strict_json_object(receipt.json_output)


def _doctor_facts(receipt: CommandReceipt) -> tuple[bool, bool, str | None, str | None, tuple[str, ...]]:
    document = _json_output(receipt)
    if document is None:
        return False, False, None, None, ("DOCTOR_RECEIPT_INVALID",)
    result = document.get("result")
    if not isinstance(result, dict):
        return False, False, None, None, ("DOCTOR_RESULT_INVALID",)
    checks = result.get("checks")
    if not isinstance(checks, list):
        return False, False, None, None, ("DOCTOR_CHECKS_INVALID",)
    blocked: list[str] = []
    public_boundary = False
    for row in checks:
        if not isinstance(row, dict):
            return False, False, None, None, ("DOCTOR_CHECK_INVALID",)
        check_id = row.get("check_id")
        disposition = row.get("disposition")
        if isinstance(check_id, str) and disposition == "blocked":
            blocked.append(check_id)
        if check_id == "public_import_boundary":
            public_boundary = disposition == "pass"
    profile = result.get("template_profile")
    template = result.get("template_revision")
    return (
        document.get("ok") is True, public_boundary,
        profile if isinstance(profile, str) else None,
        template if isinstance(template, str) else None, tuple(blocked),
    )


def _blocked_receipt(
    artifact: Path,
    *,
    commands: list[CommandReceipt],
    blockers: list[str],
    installed_version: str | None = None,
    module_file: str | None = None,
    installed_import_isolated: bool = False,
    template_profile: str | None = None,
    template_revision: str | None = None,
    project_created: bool = False,
    doctor_ready: bool = False,
    generated_tests_passed: bool = False,
    public_import_boundary_passed: bool = False,
) -> NpeCleanRoomReceipt:
    return NpeCleanRoomReceipt(
        schema="research-platform.npe-clean-room.v2",
        artifact_name=artifact.name,
        artifact_sha256=_sha256_file(artifact),
        artifact_size=artifact.stat().st_size,
        installed_version=installed_version,
        module_file=module_file,
        installed_import_isolated=installed_import_isolated,
        template_profile=template_profile,
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
        if not _create_venv(venv_root):
            return _blocked_receipt(
                artifact,
                commands=commands,
                blockers=["PYTHON_VENV_UNAVAILABLE"],
            )
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
            "print(json.dumps({'version':importlib.metadata.version('noetrium'),"
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

        create_argv = [
            str(research), "project", "create", "npe-reference", str(project),
            "--version", "0.0.1",
        ]
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
        doctor_ready, public_boundary, template_profile, template_revision, doctor_blockers = _doctor_facts(doctor)

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

        if not doctor_ready:
            blockers.extend(f"DOCTOR_BLOCKED:{check_id}" for check_id in doctor_blockers)
            if "level0_standard_bindings" in doctor_blockers:
                blockers.append("URE_LEVEL0_STANDARD_BINDINGS_UNAVAILABLE")
        if not tests_passed:
            blockers.append("GENERATED_TESTS_FAILED")
        if not public_boundary:
            blockers.append("PUBLIC_IMPORT_BOUNDARY_FAILED")
        if doctor_ready:
            blockers.append("REFERENCE_LIFECYCLE_DRIVER_UNAVAILABLE")

        return _blocked_receipt(
            artifact,
            commands=commands,
            blockers=blockers or ["NPE_ACCEPTANCE_INCOMPLETE"],
            installed_version=installed_version,
            module_file=module_file,
            installed_import_isolated=True,
            template_profile=template_profile,
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
