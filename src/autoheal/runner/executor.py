"""Thin subprocess wrapper shared by adapters for running test commands."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from autoheal.models import RerunResult


def run_command(cmd: list[str], cwd: Path) -> RerunResult:
    # On Windows, tools like npx/npm/pnpm resolve to a .CMD shim; CreateProcess
    # needs the fully-resolved path (with extension) to launch it without shell=True.
    resolved = shutil.which(cmd[0]) or cmd[0]
    proc = subprocess.run(
        [resolved, *cmd[1:]],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return RerunResult(passed=proc.returncode == 0, output=proc.stdout + proc.stderr)
