"""Hard guardrails on what a generated patch is allowed to do.

These are intentionally not configurable: the fix scope is limited to the single
failing test file, and the change size is capped, regardless of CLI/config input.
"""

from __future__ import annotations

import re

_DIFF_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


class UnsafePatchError(ValueError):
    pass


def check_diff_safety(diff_text: str, expected_file_path: str, max_changed_lines: int) -> None:
    if not diff_text.strip():
        raise UnsafePatchError("Diff is empty")

    touched_files = set(_DIFF_HEADER_RE.findall(diff_text))
    expected_norm = expected_file_path.replace("\\", "/")
    if touched_files != {expected_norm}:
        unexpected = touched_files - {expected_norm}
        raise UnsafePatchError(
            f"Diff touches unexpected file(s) {sorted(unexpected)}; "
            f"only {expected_norm} may be modified"
        )

    changed_lines = sum(
        1
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    if changed_lines > max_changed_lines:
        raise UnsafePatchError(
            f"Diff changes {changed_lines} lines, exceeding the cap of {max_changed_lines}"
        )
