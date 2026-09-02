from __future__ import annotations

from pathlib import Path

from noetrium_platform.foundation.governance.release.runtime.verification import SourceTreeReleaseVerifier
from noetrium_platform.foundation.governance.release.api import ReleaseVerificationReport, ReleaseVerifierPort


def build_source_tree_release_verifier(root: Path, manifest_path: Path) -> ReleaseVerifierPort:
    return SourceTreeReleaseVerifier(root, manifest_path)


def verify_source_tree_release(root: Path, manifest_path: Path) -> ReleaseVerificationReport:
    return build_source_tree_release_verifier(root, manifest_path).verify()


__all__ = ["build_source_tree_release_verifier", "verify_source_tree_release"]
