import subprocess
from pathlib import Path

import pytest

from autoheal.git_ops.branch import (
    GitOpError,
    branch_name_for,
    commit_file,
    create_branch,
    push_branch,
    slugify,
)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def repo_with_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(["init", "-q", "--bare"], remote)

    local = tmp_path / "local"
    local.mkdir()
    _git(["init", "-q"], local)
    _git(["config", "user.email", "test@example.com"], local)
    _git(["config", "user.name", "Test"], local)
    (local / "file.txt").write_text("original\n", encoding="utf-8")
    _git(["add", "."], local)
    _git(["commit", "-q", "-m", "init"], local)
    _git(["branch", "-M", "main"], local)
    _git(["remote", "add", "origin", str(remote)], local)
    _git(["push", "-q", "-u", "origin", "main"], local)

    return local


def test_create_commit_push_round_trip(repo_with_remote: Path):
    branch = branch_name_for("user can sign in")
    create_branch(repo_with_remote, branch, "main")

    (repo_with_remote / "file.txt").write_text("fixed\n", encoding="utf-8")
    commit_file(repo_with_remote, "file.txt", "fix(test): sample fix")
    push_branch(repo_with_remote, branch)

    remote_refs = subprocess.run(
        ["git", "branch", "-r"],
        cwd=repo_with_remote,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert f"origin/{branch}" in remote_refs


def test_create_branch_raises_on_unknown_base(repo_with_remote: Path):
    with pytest.raises(GitOpError):
        create_branch(repo_with_remote, "autoheal/fix-x", "does-not-exist")


def test_branch_name_for_is_slugified_and_unique():
    a = branch_name_for("User Can Sign In!")
    b = branch_name_for("User Can Sign In!")
    assert a.startswith("autoheal/fix-user-can-sign-in")
    assert a != b


def test_slugify_truncates_and_handles_empty():
    assert slugify("") == "test"
    assert len(slugify("x" * 100, max_len=10)) <= 10
