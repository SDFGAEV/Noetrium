from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from research_platform.api import ResearchFacade
from research_platform.operator.reference import ReferenceResearchApplication
from research_platform.operator.composition.research import main
from research_platform.platform.kernel.durability import ChecksummedDocumentError


def test_reference_workload_runs_full_durable_lifecycle():
    with TemporaryDirectory() as td:
        root = Path(td)
        facade = ResearchFacade(ReferenceResearchApplication(root))
        assert facade.run("reference-1").state == "running"
        assert facade.inspect("reference-1").state == "running"
        assert facade.stop("reference-1").state == "stopped"
        resumed = facade.resume("reference-1")
        assert resumed.state == "running"
        assert resumed.payload["generation"] == 2
        reconciled = facade.reconcile("reference-1")
        assert reconciled.state == "running"

        restarted = ResearchFacade(ReferenceResearchApplication(root))
        evidence = restarted.evidence("reference-1")
        assert [event["action"] for event in evidence.payload["events"]] == [
            "run",
            "stop",
            "resume",
            "reconcile",
        ]


def test_reference_workload_rejects_duplicate_run_and_corruption():
    with TemporaryDirectory() as td:
        root = Path(td)
        app = ReferenceResearchApplication(root)
        facade = ResearchFacade(app)
        facade.run("reference-2")
        with pytest.raises(ValueError, match="already exists"):
            facade.run("reference-2")

        state_path = app._path("reference-2")
        document = json.loads(state_path.read_text(encoding="utf-8"))
        document["payload"]["phase"] = "stopped"
        state_path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ChecksummedDocumentError):
            facade.inspect("reference-2")


def test_reference_workload_is_exercisable_through_installed_cli_shape(capsys):
    with TemporaryDirectory() as td:
        root = Path(td)
        config = root / "reference.json"
        config.write_text(json.dumps({"state_root": str(root / "state")}), encoding="utf-8")
        prefix = [
            "--application",
            "research_platform.operator.reference:build_reference_application",
            "--application-config",
            str(config),
        ]
        for command in ("run", "inspect", "stop", "resume", "reconcile", "evidence"):
            assert main([*prefix, command, "reference-3"]) == 0
            row = json.loads(capsys.readouterr().out)
            assert row["ok"] is True
            assert row["command"] == command
