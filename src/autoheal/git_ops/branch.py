"""Git branch/commit/push operations, shelled out to the `git` CLI."""

from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path


class GitOpError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise GitOpError(f"`git {' '.join(args)}` failed:\n{proc.stderr}")
    return proc.stdout


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:max_len] or "test"


def branch_name_for(test_name: str) -> str:
    return f"autoheal/fix-{slugify(test_name)}-{uuid.uuid4().hex[:7]}"


def create_branch(repo_root: Path, branch_name: str, base_branch: str) -> None:
    _run(["fetch", "origin", base_branch], repo_root)
    _run(["checkout", "-b", branch_name, f"origin/{base_branch}"], repo_root)


def commit_file(repo_root: Path, file_path: str, message: str) -> None:
    _run(["add", file_path], repo_root)
    _run(["-c", "user.name=autoheal-bot", "-c", "user.email=autoheal-bot@users.noreply.github.com", "commit", "-m", message], repo_root)


def push_branch(repo_root: Path, branch_name: str, remote: str = "origin") -> None:
    _run(["push", remote, branch_name], repo_root)
