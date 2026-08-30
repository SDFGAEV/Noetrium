from __future__ import annotations

from pathlib import Path
import subprocess

from research_platform.operator.api import ProjectTestReceipt
from research_platform.operator.runtime.project_subprocess import (
    isolated_environment,
    isolated_module_command,
)


def test_project(project_root: Path) -> ProjectTestReceipt:
    root = project_root.expanduser().absolute()
    if not (root / "tests").is_dir() or not (root / "src").is_dir():
        raise ValueError("project test requires generated src/ and tests/ directories")
    command = isolated_module_command(
        "unittest",
        ("discover", "-s", "tests", "-p", "test_*.py"),
        project_src=root / "src",
    )
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=isolated_environment(),
            check=False,
            timeout=120,
        )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
    return ProjectTestReceipt(str(root), command, exit_code)
