from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.governance.release.api import ReleaseManifest
from research_platform.governance.release.runtime.manifest import build_release_manifest
from scripts.verify_installed_artifact import verify_installed_artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _require_clean_source() -> tuple[str, str]:
    dirty = _git("status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise RuntimeError("formal distribution release requires a clean source tree")
    return _git("rev-parse", "HEAD"), _git("branch", "--show-current")


def _assert_source_identity(expected_sha: str, expected_branch: str) -> None:
    dirty = _git("status", "--porcelain=v1", "--untracked-files=all")
    observed_sha = _git("rev-parse", "HEAD")
    observed_branch = _git("branch", "--show-current")
    if dirty or observed_sha != expected_sha or observed_branch != expected_branch:
        raise RuntimeError("source identity drifted during formal distribution qualification")


def _git_archive(sha: str) -> bytes:
    completed = subprocess.run(
        ["git", "archive", "--format=tar", sha],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", "replace").strip() or "git archive failed")
    return completed.stdout


def _materialize_exact_source(sha: str, destination: Path) -> str:
    raw = _git_archive(sha)
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if not member.name or member.name.startswith("/") or ".." in parts:
                raise RuntimeError(f"unsafe git archive member: {member.name!r}")
        archive.extractall(destination, filter="data")
    return hashlib.sha256(raw).hexdigest()


def _build_distributions(
    output: Path, *, sha: str
) -> tuple[Path, Path, dict[str, object], ReleaseManifest]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="research-release-source-") as td:
        source_root = Path(td) / "source"
        source_archive_sha256 = _materialize_exact_source(sha, source_root)
        manifest = build_release_manifest(source_root)
        argv = [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(output)]
        completed = subprocess.run(argv, cwd=source_root, text=True, capture_output=True, check=False)
        command = {
            "argv": argv,
            "cwd_mode": "external-git-archive",
            "source_sha": sha,
            "source_archive_sha256": source_archive_sha256,
            "returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        }
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-4000:] or completed.stdout[-4000:] or "distribution build failed")
    wheels = tuple(output.glob("*.whl"))
    sdists = tuple(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError("distribution build must produce exactly one wheel and one sdist")
    return wheels[0], sdists[0], command, manifest


def _write_text_lf(path: Path, value: str) -> str:
    if "\r" in value:
        raise ValueError("release authority text must not contain carriage returns")
    raw = value.encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: object) -> str:
    return _write_text_lf(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _spdx_document(*, sha: str, version: str, artifacts: tuple[Path, ...]) -> dict:
    files = []
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package"}]
    for index, artifact in enumerate(artifacts, start=1):
        spdx_id = f"SPDXRef-Artifact-{index}"
        files.append({"fileName": artifact.name, "SPDXID": spdx_id, "checksums": [{"algorithm": "SHA256", "checksumValue": _sha256(artifact)}], "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"})
        relationships.append({"spdxElementId": "SPDXRef-Package", "relationshipType": "CONTAINS", "relatedSpdxElement": spdx_id})
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"research-platform-{version}",
        "documentNamespace": f"https://spdx.org/spdxdocs/research-platform-{sha}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: research-platform-release-distribution"],
        },
        "packages": [{
            "name": "research-platform",
            "SPDXID": "SPDXRef-Package",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
        }],
        "files": files,
        "relationships": relationships,
    }


def build_distribution_release(output: Path) -> dict:
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("distribution output must be outside the source tree")
    sha, branch = _require_clean_source()
    wheel, sdist, build_command, manifest = _build_distributions(output, sha=sha)
    _assert_source_identity(sha, branch)

    verification_refs: dict[str, dict[str, str]] = {}
    for kind, artifact in (("wheel", wheel), ("sdist", sdist)):
        receipt = verify_installed_artifact(artifact)
        path = output / f"{kind}-installed-verification.json"
        digest = _write_json(path, asdict(receipt))
        verification_refs[kind] = {"path": path.name, "sha256": digest}

    sbom_path = output / "SBOM.spdx.json"
    sbom_sha = _write_json(
        sbom_path,
        _spdx_document(sha=sha, version=manifest.platform_code_version, artifacts=(wheel, sdist)),
    )
    checksum_rows = []
    for artifact in (wheel, sdist, sbom_path):
        checksum_rows.append(f"{_sha256(artifact)}  {artifact.name}")
    checksums_path = output / "SHA256SUMS"
    checksums_sha = _write_text_lf(checksums_path, "\n".join(checksum_rows) + "\n")

    artifacts = {
        path.name: {"sha256": _sha256(path), "size": path.stat().st_size}
        for path in (wheel, sdist, sbom_path, checksums_path)
    }
    evidence = {
        "schema": "research-platform.distribution-release.v2",
        "manifest_source": "external-git-archive",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": "agent-research-platform-system",
        "branch": branch,
        "source_sha": sha,
        "source_tree_sha256": manifest.source_tree_sha256,
        "release_manifest_digest": manifest.digest(),
        "platform_version": manifest.platform_code_version,
        "python_requires": manifest.python_requires,
        "build_command": build_command,
        "installed_verification": verification_refs,
        "artifacts": artifacts,
        "sbom_sha256": sbom_sha,
        "checksums_sha256": checksums_sha,
    }
    evidence_path = output / "DISTRIBUTION_RELEASE_EVIDENCE.json"
    evidence_sha = _write_json(evidence_path, evidence)
    sidecar = output / "DISTRIBUTION_RELEASE_EVIDENCE.json.sha256"
    _write_text_lf(
        sidecar,
        f"{evidence_sha}  {evidence_path.name}\n",
    )
    try:
        _assert_source_identity(sha, branch)
    except Exception:
        evidence_path.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = build_distribution_release(args.output)
    except Exception as exc:
        print(f"DISTRIBUTION_RELEASE_FAIL {type(exc).__qualname__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
