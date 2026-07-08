"""Strips secrets/credentials out of text before it's sent to an external LLM API."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Bearer tokens (must run before the generic key/value pattern below, which
    # would otherwise match "Authorization: Bearer" and stop short of the token)
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer [REDACTED]"),
    # JWTs
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED_JWT]"),
    # AWS access key IDs
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    # URLs with embedded basic-auth credentials
    (re.compile(r"https?://[^:\s/@]+:[^@\s]+@"), "https://[REDACTED]@"),
    # key/value style secrets: api_key=..., password: "...", Authorization: ...
    (
        re.compile(
            r'(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|authorization)\b'
            r'\s*[:=]\s*["\']?[^\s"\']{6,}["\']?'
        ),
        r"\1=[REDACTED]",
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
