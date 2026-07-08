"""Core data structures shared across adapters, the LLM client, and the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FixType(str, Enum):
    SELECTOR_UPDATE = "selector_update"
    TIMING_WAIT = "timing_wait"
    ASSERTION_UPDATE = "assertion_update"
    TEST_DATA = "test_data"
    NO_FIX_POSSIBLE = "no_fix_possible"


@dataclass
class FailureReport:
    """A single failing test, normalized across frameworks/languages."""

    test_id: str
    """Adapter-specific unique identifier used to rerun exactly this test."""
    test_name: str
    file_path: str
    """Path to the test source file, relative to the repo root."""
    framework: str
    language: str
    error_message: str
    stack_trace: str = ""
    line: int | None = None
    attachments: dict[str, str] = field(default_factory=dict)
    """e.g. {"screenshot": "...png", "trace": "...zip"}"""


@dataclass
class SourceContext:
    """Source snippet handed to the LLM alongside the failure."""

    file_path: str
    language: str
    full_text: str
    snippet: str
    snippet_start_line: int


@dataclass
class Diagnosis:
    """Parsed, validated response from the LLM."""

    root_cause: str
    confidence: Confidence
    fix_type: FixType
    explanation: str
    diff: str | None = None


@dataclass
class RerunResult:
    passed: bool
    output: str


@dataclass
class FixAttempt:
    attempt_number: int
    diagnosis: Diagnosis
    applied: bool = False
    rerun: RerunResult | None = None
    error: str | None = None
    """Set if applying the patch or rerunning raised an exception."""


@dataclass
class HealResult:
    failure: FailureReport
    attempts: list[FixAttempt] = field(default_factory=list)
    healed: bool = False
    pr_url: str | None = None
    summary: str = ""
