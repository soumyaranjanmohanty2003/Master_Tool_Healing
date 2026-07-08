import subprocess
from pathlib import Path

import pytest

from autoheal.patch.differ import PatchApplyError, apply_diff, compute_diff, revert_diff


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    test_file = tmp_path / "example.spec.ts"
    test_file.write_text("test('a', () => {\n  click('text=Log In');\n});\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_compute_diff_produces_unified_diff():
    diff = compute_diff("a\nb\n", "a\nc\n", "example.spec.ts")
    assert "--- a/example.spec.ts" in diff
    assert "+++ b/example.spec.ts" in diff
    assert "-b" in diff
    assert "+c" in diff


def test_apply_diff_writes_file_and_revert_restores(git_repo: Path):
    original = (git_repo / "example.spec.ts").read_text(encoding="utf-8")
    fixed = original.replace("Log In", "Sign In")
    diff = compute_diff(original, fixed, "example.spec.ts")

    apply_diff(git_repo, diff)
    assert (git_repo / "example.spec.ts").read_text(encoding="utf-8") == fixed

    revert_diff(git_repo, diff)
    assert (git_repo / "example.spec.ts").read_text(encoding="utf-8") == original


def test_compute_diff_ignores_missing_trailing_newline(git_repo: Path):
    original = (git_repo / "example.spec.ts").read_text(encoding="utf-8")
    expected = original.replace("Log In", "Sign In")
    fixed = expected.rstrip("\n")  # drop trailing newline, like an LLM often does

    diff = compute_diff(original, fixed, "example.spec.ts")

    apply_diff(git_repo, diff)
    assert (git_repo / "example.spec.ts").read_text(encoding="utf-8") == expected


def test_apply_diff_raises_on_conflicting_patch(git_repo: Path):
    stale_diff = compute_diff("totally\ndifferent\ncontent\n", "totally\nchanged\ncontent\n", "example.spec.ts")
    with pytest.raises(PatchApplyError):
        apply_diff(git_repo, stale_diff)
