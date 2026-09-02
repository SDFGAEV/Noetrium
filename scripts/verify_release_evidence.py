from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from noetrium_platform.foundation.kernel.composition.release_quality import build_release_quality_evidence
from noetrium_platform.foundation.governance.release.runtime.evidence import RELEASE_EVIDENCE_FILENAME, verify_release_evidence
from noetrium_platform.foundation.governance.release.runtime.manifest import verify_release_manifest
from noetrium_platform.foundation.governance.release.runtime.freeze_lock import ReleaseFreezeBusy, ReleaseFreezeLock
from noetrium_platform.foundation.governance.release.runtime.authority import ReleaseAuthorityMismatch, load_verified_release_authority


def _verify_locked() -> int:
    evidence_path = ROOT / RELEASE_EVIDENCE_FILENAME
    manifest_path = ROOT / "RELEASE_MANIFEST.json"
    if not evidence_path.exists():
        print("RELEASE_EVIDENCE_VERIFY_FAIL missing RELEASE_EVIDENCE.json")
        return 1
    if not manifest_path.exists():
        print("RELEASE_EVIDENCE_VERIFY_FAIL missing RELEASE_MANIFEST.json")
        return 1
    try:
        manifest, evidence, authority = load_verified_release_authority(ROOT)
    except ReleaseAuthorityMismatch as exc:
        print(f"RELEASE_EVIDENCE_VERIFY_FAIL {exc}")
        return 1
    errors = list(verify_release_manifest(ROOT, manifest))
    if evidence.release_manifest_digest != manifest.digest():
        errors.append("release evidence does not bind RELEASE_MANIFEST.json")
    errors.extend(verify_release_evidence(ROOT, evidence, quality=build_release_quality_evidence(ROOT)))
    for error in errors:
        print(f"RELEASE_EVIDENCE_VERIFY_FAIL {error}")
    if errors:
        return 1
    print(f"RELEASE_MANIFEST_VERIFY_PASS {manifest.digest()}")
    print(f"RELEASE_EVIDENCE_VERIFY_PASS {evidence.digest()}")
    print(f"RELEASE_AUTHORITY_VERIFY_PASS {authority.digest()}")
    return 0


def main() -> int:
    try:
        with ReleaseFreezeLock(ROOT):
            return _verify_locked()
    except ReleaseFreezeBusy:
        print("RELEASE_EVIDENCE_VERIFY_FAIL another release freeze operation is already active")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
