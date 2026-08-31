from __future__ import annotations

from research_platform.operator.maintenance.composition.cli import main as manage_main
from research_platform.operator.runtime.research_cli import run_research_cli

from .cli import main as diagnose_main


def main(argv: list[str] | None = None) -> int:
    return run_research_cli(
        argv,
        diagnose_main=diagnose_main,
        manage_main=manage_main,
    )


__all__ = ["main"]
