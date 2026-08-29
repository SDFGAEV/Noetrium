from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import scripts.release_distribution as distribution
from scripts.verify_installed_artifact import verify_installed_artifact


def test_formal_distribution_requires_clean_exact_git_source(monkeypatch):
    def dirty_git(*args: str) -> str:
        if args[:2] == ("status", "--porcelain=v1"):
            return " M research_platform/api.py"
        raise AssertionError(args)

    monkeypatch.setattr(distribution, "_git", dirty_git)
    with pytest.raises(RuntimeError, match="clean source tree"):
        distribution._require_clean_source()


def test_clean_source_identity_returns_exact_sha_and_branch(monkeypatch):
    values = {
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("rev-parse", "HEAD"): "a" * 40,
        ("branch", "--show-current"): "system/06-product-assurance-convergence",
    }
    monkeypatch.setattr(distribution, "_git", lambda *args: values[args])
    assert distribution._require_clean_source() == ("a" * 40, "system/06-product-assurance-convergence")


def test_spdx_binds_distribution_artifact_sha256():
    local_root = distribution.ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="spdx-test-", dir=local_root) as td:
        artifact = Path(td) / "research_platform.whl"
        artifact.write_bytes(b"wheel-bytes")
        document = distribution._spdx_document(
            sha="b" * 40,
            version="9.9.9",
            artifacts=(artifact,),
        )
        assert document["documentNamespace"].endswith("b" * 40)
        checksum = document["files"][0]["checksums"][0]["checksumValue"]
        assert checksum == hashlib.sha256(b"wheel-bytes").hexdigest()
        assert document["packages"][0]["licenseDeclared"] == "NOASSERTION"


def test_distribution_output_must_be_outside_source_tree():
    with pytest.raises(ValueError, match="outside the source tree"):
        distribution.build_distribution_release(distribution.ROOT / "dist-role06")


def test_installed_artifact_verifier_rejects_missing_file():
    with pytest.raises(FileNotFoundError):
        verify_installed_artifact(distribution.ROOT / ".local" / "missing-role06.whl")


def test_release_authority_text_writer_uses_portable_lf_bytes():
    local_root = distribution.ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="release-lf-", dir=local_root) as td:
        path = Path(td) / "SHA256SUMS"
        digest = distribution._write_text_lf(path, "abc  artifact.whl\ndef  artifact.tar.gz\n")
        raw = path.read_bytes()
        assert raw == b"abc  artifact.whl\ndef  artifact.tar.gz\n"
        assert b"\r" not in raw
        assert digest == hashlib.sha256(raw).hexdigest()


def test_release_authority_text_writer_rejects_carriage_returns():
    local_root = distribution.ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="release-cr-", dir=local_root) as td:
        path = Path(td) / "SHA256SUMS"
        with pytest.raises(ValueError, match="carriage returns"):
            distribution._write_text_lf(path, "abc  artifact.whl\r\n")
        assert not path.exists()


def test_distribution_build_runs_from_external_exact_source(monkeypatch):
    local_root = distribution.ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    seen: dict[str, Path] = {}

    def fake_materialize(sha: str, destination: Path) -> str:
        assert sha == "a" * 40
        destination.mkdir(parents=True, exist_ok=False)
        seen["source"] = destination.resolve()
        return "b" * 64

    def fake_run(argv, *, cwd, text, capture_output, check):
        source_root = Path(cwd).resolve()
        assert source_root == seen["source"]
        assert source_root != distribution.ROOT
        assert distribution.ROOT not in source_root.parents
        output = Path(argv[-1])
        (output / "research_platform-1.0-py3-none-any.whl").write_bytes(b"wheel")
        (output / "research_platform-1.0.tar.gz").write_bytes(b"sdist")
        return type("Completed", (), {
            "returncode": 0,
            "stdout": "build-ok",
            "stderr": "",
        })()

    monkeypatch.setattr(distribution, "_materialize_exact_source", fake_materialize)
    monkeypatch.setattr(distribution.subprocess, "run", fake_run)
    with TemporaryDirectory(prefix="release-build-test-", dir=local_root) as td:
        output = Path(td) / "dist"
        wheel, sdist, receipt = distribution._build_distributions(
            output,
            sha="a" * 40,
        )
    assert wheel.name.endswith(".whl")
    assert sdist.name.endswith(".tar.gz")
    assert receipt["cwd_mode"] == "external-git-archive"
    assert receipt["source_sha"] == "a" * 40
    assert receipt["source_archive_sha256"] == "b" * 64


def test_exact_source_materialization_uses_safe_tar_filter(monkeypatch):
    buffer = distribution.io.BytesIO()
    payload = b"release-source"
    with distribution.tarfile.open(fileobj=buffer, mode="w") as archive:
        member = distribution.tarfile.TarInfo("README.md")
        member.size = len(payload)
        archive.addfile(member, distribution.io.BytesIO(payload))
    raw = buffer.getvalue()
    seen: dict[str, object] = {}

    def fake_extractall(self, path, members=None, *, numeric_owner=False, filter=None):
        seen["filter"] = filter

    monkeypatch.setattr(distribution, "_git_archive", lambda sha: raw)
    monkeypatch.setattr(distribution.tarfile.TarFile, "extractall", fake_extractall)
    local_root = distribution.ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="release-safe-tar-", dir=local_root) as td:
        destination = Path(td) / "source"
        digest = distribution._materialize_exact_source("a" * 40, destination)
    assert seen["filter"] == "data"
    assert digest == hashlib.sha256(raw).hexdigest()
