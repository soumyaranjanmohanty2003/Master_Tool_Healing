"""The heal loop: detect -> diagnose -> patch -> rerun -> retry/give up -> PR."""

from __future__ import annotations

import logging
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter
from autoheal.adapters.detect import detect_adapter
from autoheal.config import AutoHealConfig
from autoheal.context.collector import collect_source_context
from autoheal.git_ops.branch import branch_name_for, commit_file, create_branch, push_branch
from autoheal.git_ops.pr import open_pull_request
from autoheal.llm.groq_client import DiagnosisError, GroqDiagnosisClient
from autoheal.models import FailureReport, FixAttempt, FixType, HealResult
from autoheal.patch.differ import PatchApplyError, apply_diff, revert_diff
from autoheal.patch.safety import UnsafePatchError, check_diff_safety

log = logging.getLogger("autoheal")


def heal(config: AutoHealConfig) -> list[HealResult]:
    adapter = detect_adapter(config.repo_root, config.results_file)
    results_path = Path(config.results_file) if config.results_file else adapter.run_suite()
    failures = adapter.parse_results(results_path)

    if not failures:
        log.info("No failing tests found.")
        return []

    llm_client = GroqDiagnosisClient(config.groq_api_key, config.groq_model)
    return [heal_one(config, adapter, llm_client, failure) for failure in failures]


def heal_one(
    config: AutoHealConfig,
    adapter: TestFrameworkAdapter,
    llm_client: GroqDiagnosisClient,
    failure: FailureReport,
) -> HealResult:
    result = HealResult(failure=failure)

    for attempt_num in range(1, config.max_attempts + 1):
        context = collect_source_context(config.repo_root, failure)

        try:
            diagnosis = llm_client.diagnose(failure, context, list(result.attempts))
        except DiagnosisError as exc:
            result.summary = f"LLM diagnosis failed: {exc}"
            log.info("Attempt %d: %s", attempt_num, result.summary)
            break

        log.info(
            "Attempt %d: diagnosis fix_type=%s confidence=%s root_cause=%s",
            attempt_num, diagnosis.fix_type.value, diagnosis.confidence.value, diagnosis.root_cause,
        )

        attempt = FixAttempt(attempt_number=attempt_num, diagnosis=diagnosis)
        result.attempts.append(attempt)

        if diagnosis.fix_type == FixType.NO_FIX_POSSIBLE or not diagnosis.diff:
            result.summary = f"No fix attempted (attempt {attempt_num}): {diagnosis.root_cause}"
            log.info("Attempt %d: no diff produced, stopping", attempt_num)
            break

        try:
            check_diff_safety(diagnosis.diff, failure.file_path, config.max_changed_lines)
        except UnsafePatchError as exc:
            attempt.error = f"Rejected unsafe patch: {exc}"
            log.info("Attempt %d: %s", attempt_num, attempt.error)
            continue

        try:
            apply_diff(config.repo_root, diagnosis.diff)
            attempt.applied = True
        except PatchApplyError as exc:
            attempt.error = str(exc)
            log.info("Attempt %d: patch failed to apply: %s", attempt_num, exc)
            log.info("Attempt %d: diff was:\n%s", attempt_num, diagnosis.diff)
            continue

        attempt.rerun = adapter.run_single(failure)

        if attempt.rerun.passed:
            result.healed = True
            result.summary = f"Healed on attempt {attempt_num}: {diagnosis.root_cause}"
            log.info("Attempt %d: rerun passed, test healed", attempt_num)
            if not config.dry_run:
                result.pr_url = _open_pr(config, failure, attempt)
            return result

        log.info(
            "Attempt %d: patch applied but rerun still failed: %s",
            attempt_num, (attempt.rerun.output or "")[:1000],
        )
        revert_diff(config.repo_root, diagnosis.diff)

    if not result.summary:
        result.summary = f"Could not heal after {len(result.attempts)} attempt(s)"
    return result


def _open_pr(config: AutoHealConfig, failure: FailureReport, attempt: FixAttempt) -> str:
    branch = branch_name_for(failure.test_name)
    create_branch(config.repo_root, branch, config.base_branch)
    commit_file(
        config.repo_root,
        failure.file_path,
        f"fix(test): auto-heal {failure.test_name}",
    )
    push_branch(config.repo_root, branch)

    return open_pull_request(
        repo=config.github_repo,
        token=config.github_token,
        head_branch=branch,
        base_branch=config.base_branch,
        title=f"AutoHeal: fix {failure.test_name}",
        body=_pr_body(failure, attempt),
        labels=config.pr_labels,
    )


def _pr_body(failure: FailureReport, attempt: FixAttempt) -> str:
    diagnosis = attempt.diagnosis
    return f"""## AutoHeal auto-generated fix

**Test:** `{failure.test_name}`
**File:** `{failure.file_path}`
**Attempts:** {attempt.attempt_number}
**Confidence:** {diagnosis.confidence.value}

### Root cause
{diagnosis.root_cause}

### Fix
{diagnosis.explanation}

<details>
<summary>Diff</summary>

```diff
{diagnosis.diff}
```

</details>

---
This PR was automatically generated by [AutoHeal](https://github.com) after the \
original test failed in CI, the fix was applied, and the test was rerun \
successfully. Please review before merging.
"""
