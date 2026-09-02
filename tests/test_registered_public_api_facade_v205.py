from pathlib import Path

from noetrium_platform.foundation.governance.architecture.public_api_invariants import audit_registered_public_facades


def test_registered_boundaries_do_not_reexport_concrete_layers():
    root = Path(__file__).resolve().parents[1]
    assert audit_registered_public_facades(root) == []
