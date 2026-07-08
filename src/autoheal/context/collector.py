"""Builds the source-code context handed to the LLM for a given failure."""

from __future__ import annotations

from pathlib import Path

from autoheal.context.redaction import redact
from autoheal.models import FailureReport, SourceContext

DEFAULT_CONTEXT_LINES = 40


def collect_source_context(
    repo_root: Path,
    failure: FailureReport,
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> SourceContext:
    file_path = repo_root / failure.file_path
    full_text = file_path.read_text(encoding="utf-8")
    lines = full_text.splitlines()

    if failure.line and 0 < failure.line <= len(lines):
        start = max(1, failure.line - context_lines)
        end = min(len(lines), failure.line + context_lines)
    else:
        start, end = 1, len(lines)

    snippet = "\n".join(lines[start - 1 : end])

    return SourceContext(
        file_path=failure.file_path,
        language=failure.language,
        full_text=redact(full_text),
        snippet=redact(snippet),
        snippet_start_line=start,
    )
