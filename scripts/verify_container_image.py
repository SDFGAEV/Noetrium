from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ACTIONS = ("run", "inspect", "stop", "resume", "reconcile", "evidence")
_MARKER = "CONTAINER_PRODUCT_SMOKE="


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    argv: tuple[str, ...]
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True, slots=True)
class ContainerVerificationReceipt:
    schema: str
    image: str
    image_id: str
    source_sha: str
    repo_digests: tuple[str, ...]
    container_user: str
    python_version: str
    package_version: str
    module_file: str
    actions: tuple[str, ...]
    commands: tuple[CommandReceipt, ...]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _receipt(argv: list[str], completed: subprocess.CompletedProcess[str]) -> CommandReceipt:
    return CommandReceipt(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout_sha256=_digest(completed.stdout),
        stderr_sha256=_digest(completed.stderr),
        stdout_tail=completed.stdout[-4000:],
        stderr_tail=completed.stderr[-4000:],
    )


def _run(argv: list[str]) -> tuple[CommandReceipt, str]:
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    receipt = _receipt(argv, completed)
    if completed.returncode != 0:
        raise RuntimeError(
            "container verification command failed: "
            + " ".join(argv)
            + f"\nstdout={completed.stdout[-4000:]}\nstderr={completed.stderr[-4000:]}"
        )
    return receipt, completed.stdout


def _product_smoke_script() -> str:
    return r'''set -eu
research --help >/dev/null
work="$(mktemp -d)"
python - "$work" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
(root / "reference.json").write_text(
    json.dumps({"state_root": str(root / "state")}),
    encoding="utf-8",
)
PY
for action in run inspect stop resume reconcile evidence; do
  research --application research_platform.operator.reference:build_reference_application \
    --application-config "$work/reference.json" "$action" container-reference > "$work/$action.json"
done
python - "$work" <<'PY'
import importlib.metadata
import json
import sys
from pathlib import Path
import research_platform.api
root = Path(sys.argv[1])
actions = ("run", "inspect", "stop", "resume", "reconcile", "evidence")
for action in actions:
    payload = json.loads((root / f"{action}.json").read_text(encoding="utf-8"))
    if payload.get("ok") is not True or payload.get("command") != action:
        raise SystemExit(f"invalid container lifecycle receipt: {action}")
print("CONTAINER_PRODUCT_SMOKE=" + json.dumps({
    "actions": actions,
    "module_file": research_platform.api.__file__,
    "package_version": importlib.metadata.version("research-platform"),
    "python_version": sys.version.split()[0],
}, sort_keys=True))
PY
'''


def _parse_smoke(stdout: str) -> dict[str, object]:
    lines = [line for line in stdout.splitlines() if line.startswith(_MARKER)]
    if len(lines) != 1:
        raise RuntimeError("container smoke output must contain exactly one product marker")
    payload = json.loads(lines[0][len(_MARKER):])
    if not isinstance(payload, dict):
        raise RuntimeError("container smoke marker must contain a JSON object")
    return payload

def verify_container_image(image: str, *, expected_source_sha: str) -> ContainerVerificationReceipt:
    source_sha = expected_source_sha.strip().lower()
    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("expected source SHA must be a 40-character lowercase Git SHA")
    if not image.strip():
        raise ValueError("container image must not be blank")

    receipts: list[CommandReceipt] = []
    inspect_receipt, inspect_stdout = _run(["docker", "image", "inspect", image])
    receipts.append(inspect_receipt)
    document = json.loads(inspect_stdout)
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise RuntimeError("docker image inspect returned an invalid document")
    metadata = document[0]
    labels = metadata.get("Config", {}).get("Labels") or {}
    if labels.get("org.opencontainers.image.revision") != source_sha:
        raise RuntimeError("container source revision label does not match expected SHA")
    image_id = metadata.get("Id")
    if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
        raise RuntimeError("container image ID is missing or invalid")
    repo_digests = metadata.get("RepoDigests") or []
    if not isinstance(repo_digests, list) or not all(isinstance(value, str) for value in repo_digests):
        raise RuntimeError("container RepoDigests field is invalid")
    config = metadata.get("Config")
    if not isinstance(config, dict):
        raise RuntimeError("container Config field is invalid")
    container_user = config.get("User")
    if not isinstance(container_user, str) or not container_user.strip():
        raise RuntimeError("container image must declare a non-root user")
    principal = container_user.strip().split(":", 1)[0].lower()
    if principal in {"0", "root"}:
        raise RuntimeError("container image must not run as root")

    doctor_receipt, _ = _run(["docker", "run", "--rm", "--network=none", image, "doctor"])
    receipts.append(doctor_receipt)
    smoke_receipt, smoke_stdout = _run(
        ["docker", "run", "--rm", "--network=none", image, "shell", "/bin/sh", "-lc", _product_smoke_script()]
    )
    receipts.append(smoke_receipt)
    smoke = _parse_smoke(smoke_stdout)
    actions = smoke.get("actions")
    if actions != list(_ACTIONS):
        raise RuntimeError("container smoke did not exercise the full lifecycle")
    module_file = smoke.get("module_file")
    if not isinstance(module_file, str) or "/site-packages/" not in module_file.replace("\\", "/"):
        raise RuntimeError("container product import did not come from installed site-packages")
    package_version = smoke.get("package_version")
    python_version = smoke.get("python_version")
    if not isinstance(package_version, str) or not package_version:
        raise RuntimeError("container package version missing")
    if not isinstance(python_version, str) or not python_version.startswith("3.12."):
        raise RuntimeError("container Python runtime is not Python 3.12")

    return ContainerVerificationReceipt(
        schema="research-platform.container-verification.v1",
        image=image,
        image_id=image_id,
        source_sha=source_sha,
        repo_digests=tuple(repo_digests),
        container_user=container_user.strip(),
        python_version=python_version,
        package_version=package_version,
        module_file=module_file,
        actions=tuple(actions),
        commands=tuple(receipts),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = verify_container_image(
            args.image,
            expected_source_sha=args.expected_source_sha,
        )
    except Exception as exc:
        print(f"CONTAINER_VERIFY_FAIL {type(exc).__qualname__}: {exc}", file=sys.stderr)
        return 1
    document = json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
    print(document, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
