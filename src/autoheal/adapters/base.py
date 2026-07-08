"""Common interface every test-framework adapter implements.

An adapter's job is narrow on purpose: turn a framework/language's native results
format into the shared `FailureReport` shape, and know how to rerun exactly one
test. Everything downstream (context building, LLM diagnosis, patching, PR
creation) is adapter-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from autoheal.models import FailureReport, RerunResult


def resolve_repo_relative_path(raw_file: str, external_root: str | None, repo_root: Path) -> str:
    """Resolves a path reported by a test runner - which may be relative to
    that runner's own notion of "root" (Playwright's `config.rootDir`,
    pytest's `root`), not necessarily `repo_root` - into a path relative to
    `repo_root`. Falls back to the raw value if it can't be resolved (e.g. it
    already was repo-relative, or points outside the repo).
    """
    if not raw_file:
        return raw_file
    candidate = Path(raw_file)
    if not candidate.is_absolute() and external_root:
        candidate = Path(external_root) / raw_file
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return raw_file


class TestFrameworkAdapter(ABC):
    name: str
    language: str

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    @abstractmethod
    def run_suite(self) -> Path:
        """Run the full suite and return the path to a results file.

        Used when no pre-generated results file was supplied to the CLI.
        """

    @abstractmethod
    def parse_results(self, results_path: Path) -> list[FailureReport]:
        """Parse a results file into normalized failure reports (empty list if
        everything passed)."""

    @abstractmethod
    def run_single(self, failure: FailureReport) -> RerunResult:
        """Rerun exactly the one failing test identified by `failure.test_id`."""
