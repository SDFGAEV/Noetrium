from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def _build_distributions(output: Path) -> tuple[Path, Path, dict[str, object]]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    argv = [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(output)]
    completed = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    command = {
        "argv": argv,
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
    return wheels[0], sdists[0], command


def _write_json(path: Path, payload: object) -> str:
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


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
    manifest = build_release_manifest(ROOT)
    wheel, sdist, build_command = _build_distributions(output)
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("distribution build mutated tracked/untracked source state")

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
    checksums_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    checksums_sha = _sha256(checksums_path)

    artifacts = {
        path.name: {"sha256": _sha256(path), "size": path.stat().st_size}
        for path in (wheel, sdist, sbom_path, checksums_path)
    }
    evidence = {
        "schema": "research-platform.distribution-release.v1",
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
    (output / "DISTRIBUTION_RELEASE_EVIDENCE.json.sha256").write_text(
        f"{evidence_sha}  {evidence_path.name}\n", encoding="utf-8"
    )
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
