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
