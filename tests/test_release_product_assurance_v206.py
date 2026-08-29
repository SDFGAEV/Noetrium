from __future__ import annotations

import hashlib

import scripts.product_assurance_gate as assurance


def _receipt(name: str, argv: list[str], returncode: int) -> assurance.GateCommandReceipt:
    empty = hashlib.sha256(b"").hexdigest()
    return assurance.GateCommandReceipt(
        name=name,
        argv=tuple(argv),
        returncode=returncode,
        stdout_sha256=empty,
        stderr_sha256=empty,
        stdout_tail="",
        stderr_tail="",
    )


def test_product_assurance_gate_fails_fast_on_blocker(monkeypatch):
    calls: list[str] = []

    def fake_run(name: str, argv: list[str]):
        calls.append(name)
        return _receipt(name, argv, 1 if name == "provider-conformance" else 0)

    monkeypatch.setattr(assurance, "_run", fake_run)
    result = assurance.evaluate(full=True)
    assert result.passed is False
    assert calls == ["test-taxonomy", "provider-conformance"]


def test_full_assurance_uses_worktree_local_pytest_basetemp(monkeypatch):
    commands: list[tuple[str, list[str]]] = []

    def fake_run(name: str, argv: list[str]):
        commands.append((name, argv))
        return _receipt(name, argv, 0)

    monkeypatch.setattr(assurance, "_run", fake_run)
    result = assurance.evaluate(full=True)
    assert result.passed is True
    assert [name for name, _ in commands] == [
        "test-taxonomy",
        "provider-conformance",
        "architecture",
        "full-regression",
    ]
    full_argv = commands[-1][1]
    index = full_argv.index("--basetemp")
    assert ".local" in full_argv[index + 1]
    assert "product-assurance-full" in full_argv[index + 1]
