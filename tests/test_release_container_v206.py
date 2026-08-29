from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scripts.verify_container_image as container

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def _receipt(argv: list[str]) -> container.CommandReceipt:
    empty = hashlib.sha256(b"").hexdigest()
    return container.CommandReceipt(
        argv=tuple(argv),
        returncode=0,
        stdout_sha256=empty,
        stderr_sha256=empty,
        stdout_tail="",
        stderr_tail="",
    )


def test_container_definition_binds_source_and_doctor_checks_product_cli():
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "deploy" / "container-entrypoint.sh").read_text(encoding="utf-8")
    assert "ARG PLATFORM_SOURCE_SHA=unknown" in dockerfile
    assert 'org.opencontainers.image.revision="${PLATFORM_SOURCE_SHA}"' in dockerfile
    assert "research --help >/dev/null" in entrypoint
    assert "USER platform" in dockerfile
    assert "FROM python:3.12-slim-bookworm AS builder" in dockerfile
    runtime_stage = dockerfile.split("FROM python:3.12-slim-bookworm", 2)[-1]
    assert "COPY research_platform" not in runtime_stage
    assert "COPY --from=builder /wheelhouse /tmp/wheelhouse" in runtime_stage
    assert "research_platform-*.whl" in runtime_stage
    assert "research-platform-architecture-gate" in entrypoint
    assert "$PACKAGE_ROOT/environment/minecraft" in entrypoint


def test_container_smoke_script_exercises_full_reference_lifecycle():
    script = container._product_smoke_script()
    assert "research --help" in script
    for action in container._ACTIONS:
        assert action in script
    assert "research_platform.operator.reference:build_reference_application" in script


def test_container_verifier_rejects_source_revision_drift(monkeypatch):
    document = [{
        "Id": "sha256:" + "b" * 64,
        "RepoDigests": [],
        "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
    }]

    def fake_run(argv: list[str]):
        return _receipt(argv), json.dumps(document)

    monkeypatch.setattr(container, "_run", fake_run)
    with pytest.raises(RuntimeError, match="source revision"):
        container.verify_container_image("research-platform:test", expected_source_sha=SHA)


def test_container_verifier_rejects_root_runtime_user(monkeypatch):
    document = [{
        "Id": "sha256:" + "d" * 64,
        "RepoDigests": [],
        "Config": {
            "Labels": {"org.opencontainers.image.revision": SHA},
            "User": "root",
        },
    }]

    def fake_run(argv: list[str]):
        return _receipt(argv), json.dumps(document)

    monkeypatch.setattr(container, "_run", fake_run)
    with pytest.raises(RuntimeError, match="must not run as root"):
        container.verify_container_image("research-platform:test", expected_source_sha=SHA)

def test_container_verifier_returns_exact_source_bound_receipt(monkeypatch):
    inspect_document = [{
        "Id": "sha256:" + "c" * 64,
        "RepoDigests": ["research-platform@test-digest"],
        "Config": {
            "Labels": {"org.opencontainers.image.revision": SHA},
            "User": "platform",
        },
    }]
    smoke = {
        "actions": list(container._ACTIONS),
        "module_file": "/usr/local/lib/python3.12/site-packages/research_platform/api.py",
        "package_version": "0.43.1",
        "python_version": "3.12.10",
    }
    outputs = iter((
        json.dumps(inspect_document),
        "Python 3.12.10\nplatform_state_dir=/var/lib/research-platform writable=true\n",
        container._MARKER + json.dumps(smoke) + "\n",
    ))

    def fake_run(argv: list[str]):
        return _receipt(argv), next(outputs)

    monkeypatch.setattr(container, "_run", fake_run)
    result = container.verify_container_image("research-platform:test", expected_source_sha=SHA)
    assert result.source_sha == SHA
    assert result.actions == container._ACTIONS
    assert result.package_version == "0.43.1"
    assert result.container_user == "platform"
    assert all("--network=none" in receipt.argv for receipt in result.commands[1:])
    assert len(result.commands) == 3


def test_ci_builds_and_verifies_exact_source_container():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--build-arg PLATFORM_SOURCE_SHA=\"${GITHUB_SHA}\"" in workflow
    assert 'research-platform:${GITHUB_SHA}' in workflow
    assert "scripts/verify_container_image.py" in workflow
    assert '--expected-source-sha "${GITHUB_SHA}"' in workflow
