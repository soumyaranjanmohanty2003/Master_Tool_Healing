import pytest

from autoheal.patch.differ import compute_diff
from autoheal.patch.safety import UnsafePatchError, check_diff_safety


def test_accepts_diff_touching_expected_file():
    diff = compute_diff("line1\nline2\n", "line1\nline2 changed\n", "tests/foo.spec.ts")
    check_diff_safety(diff, "tests/foo.spec.ts", max_changed_lines=200)


def test_rejects_empty_diff():
    with pytest.raises(UnsafePatchError):
        check_diff_safety("", "tests/foo.spec.ts", max_changed_lines=200)


def test_rejects_diff_touching_unexpected_file():
    diff = compute_diff("line1\n", "line1 changed\n", "tests/other.spec.ts")
    with pytest.raises(UnsafePatchError):
        check_diff_safety(diff, "tests/foo.spec.ts", max_changed_lines=200)


def test_rejects_diff_exceeding_max_changed_lines():
    original = "\n".join(f"line{i}" for i in range(50)) + "\n"
    fixed = "\n".join(f"line{i}-changed" for i in range(50)) + "\n"
    diff = compute_diff(original, fixed, "tests/foo.spec.ts")
    with pytest.raises(UnsafePatchError):
        check_diff_safety(diff, "tests/foo.spec.ts", max_changed_lines=10)
