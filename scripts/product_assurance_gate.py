from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.governance.release.runtime.manifest import build_release_manifest


@dataclass(frozen=True, slots=True)
class GateCommandReceipt:
    name: str
    argv: tuple[str, ...]
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True, slots=True)
class ProductAssuranceReceipt:
    schema: str
    generated_at_utc: str
    repository: str
    branch: str
    source_sha: str
    source_tree_sha256: str
    source_clean: bool
    passed: bool
    commands: tuple[GateCommandReceipt, ...]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:]


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _source_identity() -> tuple[str, str, str, bool]:
    sha = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    clean = not bool(
        _git("status", "--porcelain=v1", "--untracked-files=all")
    )
    source_tree_sha256 = build_release_manifest(ROOT).source_tree_sha256
    return sha, branch, source_tree_sha256, clean


def _run(name: str, argv: list[str]) -> GateCommandReceipt:
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return GateCommandReceipt(
        name=name,
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout_sha256=_digest(completed.stdout),
        stderr_sha256=_digest(completed.stderr),
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def evaluate(*, full: bool) -> ProductAssuranceReceipt:
    source_sha, branch, source_tree_sha256, source_clean = _source_identity()
    if full and not source_clean:
        return ProductAssuranceReceipt(
            schema="research-platform.product-assurance-gate.v2",
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            repository="agent-research-platform-system",
            branch=branch,
            source_sha=source_sha,
            source_tree_sha256=source_tree_sha256,
            source_clean=False,
            passed=False,
            commands=(),
        )
    commands = [
        ("test-taxonomy", [sys.executable, "scripts/test_system.py", "check"]),
        (
            "provider-conformance",
            [sys.executable, "scripts/provider_conformance.py", "run"],
        ),
        (
            "architecture",
            [sys.executable, "-m", "research_platform.governance.architecture.gate"],
        ),
    ]
    if full:
        commands.append(
            (
                "full-regression",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "--basetemp",
                    str(ROOT / ".local" / "product-assurance-full"),
                ],
            )
        )
    receipts: list[GateCommandReceipt] = []
    for name, argv in commands:
        receipt = _run(name, argv)
        receipts.append(receipt)
        if receipt.returncode != 0:
            break
    passed = (
        bool(receipts)
        and all(row.returncode == 0 for row in receipts)
        and len(receipts) == len(commands)
    )
    return ProductAssuranceReceipt(
        schema="research-platform.product-assurance-gate.v2",
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        repository="agent-research-platform-system",
        branch=branch,
        source_sha=source_sha,
        source_tree_sha256=source_tree_sha256,
        source_clean=source_clean,
        passed=passed,
        commands=tuple(receipts),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    receipt = evaluate(full=args.full)
    document = (
        json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
    print(document, end="")
    return 0 if receipt.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
