"""Prompt templates for the diagnose-and-fix step.

Design note: we ask the model for the *entire corrected file content* rather than
a hand-written unified diff. LLMs are unreliable at producing diff hunks with
correct `@@` line offsets; asking for full file content and computing the diff
ourselves (see `autoheal.patch.differ.compute_diff`) is far more robust and is
what actually gets applied.
"""

from __future__ import annotations

from autoheal.models import FailureReport, FixAttempt, SourceContext

SYSTEM_PROMPT = """\
You are AutoHeal, an assistant that diagnoses and fixes broken automated UI tests.

Rules you must follow:
1. You may ONLY modify the single test file shown to you. Never invent changes to
   other files, application source, or configuration.
2. Only propose a fix for issues caused by the TEST SCRIPT itself (e.g. a stale
   selector, a race condition/missing wait, an outdated assertion, stale test
   data). If the failure looks like a real product/application bug, or you are
   not confident about the root cause, set "fix_type" to "no_fix_possible" and
   leave "fixed_code" null - do not guess.
3. Preserve the file's existing style, imports, and structure. Change only what's
   necessary to fix the failure.
4. Respond with ONLY a single JSON object matching this schema, no prose outside it:
{
  "root_cause": "concise diagnosis of why the test failed",
  "confidence": "high" | "medium" | "low",
  "fix_type": "selector_update" | "timing_wait" | "assertion_update" | "test_data" | "no_fix_possible",
  "explanation": "1-3 sentences explaining the fix, for a PR description",
  "fixed_code": "the ENTIRE corrected file content, or null if fix_type is no_fix_possible"
}
"""


def build_user_prompt(
    failure: FailureReport,
    context: SourceContext,
    previous_attempts: list[FixAttempt] | None = None,
) -> str:
    parts = [
        f"Framework: {failure.framework}",
        f"Language: {context.language}",
        f"Test file: {context.file_path}",
        f"Failing test: {failure.test_name}",
        f"Error message:\n{failure.error_message}",
    ]
    if failure.stack_trace:
        parts.append(f"Stack trace:\n{failure.stack_trace}")

    if previous_attempts:
        parts.append("Previous fix attempts on this same failure did not work:")
        for attempt in previous_attempts:
            outcome = attempt.rerun.output if attempt.rerun else (attempt.error or "not applied")
            parts.append(
                f"- Attempt {attempt.attempt_number}: root_cause={attempt.diagnosis.root_cause!r}, "
                f"fix_type={attempt.diagnosis.fix_type.value}, rerun_output={outcome[:500]!r}"
            )
        parts.append("Consider a different root cause or approach than the attempts above.")

    parts.append(f"Full current file content ({context.file_path}):\n```\n{context.full_text}\n```")

    return "\n\n".join(parts)
