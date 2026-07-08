import subprocess
from pathlib import Path

from autoheal.config import AutoHealConfig
from autoheal.models import Confidence, Diagnosis, FailureReport, FixType, RerunResult
from autoheal.orchestrator import heal_one
from autoheal.patch.differ import compute_diff
import autoheal.orchestrator as orch

import pytest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "example.spec.ts").write_text(
        "test('x', () => { click('text=Log In'); });\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def make_failure(file_path: str = "tests/example.spec.ts") -> FailureReport:
    return FailureReport(
        test_id=f"{file_path}::user can sign in",
        test_name="user can sign in",
        file_path=file_path,
        framework="playwright",
        language="typescript",
        error_message="Timeout waiting for selector text=Log In",
    )


class FakeAdapter:
    def __init__(self, rerun_results):
        self._rerun_results = list(rerun_results)

    def run_single(self, failure):
        return self._rerun_results.pop(0)


class FakeLLMClient:
    def __init__(self, diagnoses):
        self._diagnoses = list(diagnoses)
        self.calls = []

    def diagnose(self, failure, context, previous_attempts=None):
        self.calls.append((failure, context, previous_attempts))
        return self._diagnoses.pop(0)


def fixed_diagnosis(original_text, fixed_text, file_path):
    diff = compute_diff(original_text, fixed_text, file_path)
    return Diagnosis(
        root_cause="Stale selector",
        confidence=Confidence.HIGH,
        fix_type=FixType.SELECTOR_UPDATE,
        explanation="fixed it",
        diff=diff,
    )


def no_fix_diagnosis():
    return Diagnosis(
        root_cause="Real app bug",
        confidence=Confidence.LOW,
        fix_type=FixType.NO_FIX_POSSIBLE,
        explanation="",
        diff=None,
    )


def base_config(repo_root: Path) -> AutoHealConfig:
    return AutoHealConfig(repo_root=repo_root, max_attempts=3, max_changed_lines=200, dry_run=True)


def test_heals_on_first_attempt(repo):
    failure = make_failure()
    original = (repo / failure.file_path).read_text(encoding="utf-8")
    fixed = original.replace("Log In", "Sign In")

    llm = FakeLLMClient([fixed_diagnosis(original, fixed, failure.file_path)])
    adapter = FakeAdapter([RerunResult(passed=True, output="ok")])

    result = heal_one(base_config(repo), adapter, llm, failure)

    assert result.healed is True
    assert len(result.attempts) == 1
    assert (repo / failure.file_path).read_text(encoding="utf-8") == fixed


def test_retries_then_heals(repo):
    failure = make_failure()
    original = (repo / failure.file_path).read_text(encoding="utf-8")
    bad_fix = original.replace("Log In", "Still Wrong")
    good_fix = original.replace("Log In", "Sign In")

    llm = FakeLLMClient(
        [
            fixed_diagnosis(original, bad_fix, failure.file_path),
            fixed_diagnosis(original, good_fix, failure.file_path),
        ]
    )
    adapter = FakeAdapter(
        [RerunResult(passed=False, output="still failing"), RerunResult(passed=True, output="ok")]
    )

    result = heal_one(base_config(repo), adapter, llm, failure)

    assert result.healed is True
    assert len(result.attempts) == 2
    assert (repo / failure.file_path).read_text(encoding="utf-8") == good_fix
    # the failed first attempt is fed back to the LLM as context on the retry
    assert llm.calls[1][2] == [result.attempts[0]]


def test_gives_up_when_no_fix_possible(repo):
    failure = make_failure()
    llm = FakeLLMClient([no_fix_diagnosis()])
    adapter = FakeAdapter([])

    result = heal_one(base_config(repo), adapter, llm, failure)

    assert result.healed is False
    assert "Real app bug" in result.summary
    assert len(result.attempts) == 1


def test_gives_up_after_max_attempts_and_leaves_file_untouched(repo):
    failure = make_failure()
    original = (repo / failure.file_path).read_text(encoding="utf-8")
    bad_fix = original.replace("Log In", "Still Wrong")

    llm = FakeLLMClient([fixed_diagnosis(original, bad_fix, failure.file_path) for _ in range(3)])
    adapter = FakeAdapter([RerunResult(passed=False, output="nope") for _ in range(3)])

    config = base_config(repo)
    config.max_attempts = 3
    result = heal_one(config, adapter, llm, failure)

    assert result.healed is False
    assert len(result.attempts) == 3
    assert (repo / failure.file_path).read_text(encoding="utf-8") == original


def test_rejects_unsafe_patch_touching_other_file(repo):
    failure = make_failure()
    original = (repo / failure.file_path).read_text(encoding="utf-8")
    diff = compute_diff(original, original.replace("Log In", "Sign In"), "tests/other.spec.ts")
    unsafe_diagnosis = Diagnosis(
        root_cause="x", confidence=Confidence.HIGH, fix_type=FixType.SELECTOR_UPDATE, explanation="", diff=diff
    )

    llm = FakeLLMClient([unsafe_diagnosis])
    adapter = FakeAdapter([])

    config = base_config(repo)
    config.max_attempts = 1
    result = heal_one(config, adapter, llm, failure)

    assert result.healed is False
    assert result.attempts[0].error is not None
    assert "unexpected file" in result.attempts[0].error


def test_calls_open_pr_when_not_dry_run(repo, monkeypatch):
    failure = make_failure()
    original = (repo / failure.file_path).read_text(encoding="utf-8")
    fixed = original.replace("Log In", "Sign In")

    llm = FakeLLMClient([fixed_diagnosis(original, fixed, failure.file_path)])
    adapter = FakeAdapter([RerunResult(passed=True, output="ok")])

    monkeypatch.setattr(orch, "_open_pr", lambda config, failure, attempt: "https://example.com/pr/1")

    config = base_config(repo)
    config.dry_run = False
    result = orch.heal_one(config, adapter, llm, failure)

    assert result.pr_url == "https://example.com/pr/1"
