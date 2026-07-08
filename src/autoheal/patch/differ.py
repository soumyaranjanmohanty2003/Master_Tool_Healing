"""Computing and applying unified diffs.

We compute the diff ourselves (via difflib) from the LLM's full corrected file
content rather than trusting a model-authored diff — see the note in
`autoheal.llm.prompts`. That makes `git apply` a formality: the diff is always
well-formed relative to the current file content.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import tempfile
from pathlib import Path


class PatchApplyError(RuntimeError):
    pass


def compute_diff(original: str, fixed: str, file_path: str) -> str:
    # LLM-generated file content often drops the trailing newline. difflib treats
    # the final line as changed in that case (identical text, differing only in
    # whether it ends with "\n"), and since we don't emit a "\ No newline at end
    # of file" marker, the two runs together and corrupts the patch for `git
    # apply`. Normalize to the original's convention so a missing trailing
    # newline in the LLM's output never produces a diff by itself.
    if original.endswith("\n") and not fixed.endswith("\n"):
        fixed += "\n"
    elif not original.endswith("\n") and fixed.endswith("\n"):
        fixed = fixed[:-1]

    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def _write_patch_file(diff_text: str) -> str:
    # Written via a real file (not piped through stdin) so we control the exact
    # bytes on disk: subprocess text-mode stdin silently translates "\n" to
    # os.linesep on Windows, corrupting the diff and making `git apply` reject
    # otherwise-correct patches with a spurious "does not apply" error.
    fd, path = tempfile.mkstemp(suffix=".patch")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(diff_text)
    return path


def apply_diff(repo_root: Path, diff_text: str) -> None:
    patch_path = _write_patch_file(diff_text)
    try:
        check = subprocess.run(
            ["git", "apply", "--check", patch_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            raise PatchApplyError(f"git apply --check failed:\n{check.stderr}")

        apply = subprocess.run(
            ["git", "apply", patch_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if apply.returncode != 0:
            raise PatchApplyError(f"git apply failed:\n{apply.stderr}")
    finally:
        os.unlink(patch_path)


def revert_diff(repo_root: Path, diff_text: str) -> None:
    """Best-effort revert; used when a rerun fails and we're about to retry."""
    patch_path = _write_patch_file(diff_text)
    try:
        subprocess.run(
            ["git", "apply", "-R", patch_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        os.unlink(patch_path)
