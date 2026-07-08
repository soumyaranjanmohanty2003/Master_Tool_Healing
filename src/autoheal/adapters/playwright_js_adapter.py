"""Adapter for Playwright Test (JS/TS): the `npx playwright test` runner."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter, resolve_repo_relative_path
from autoheal.models import FailureReport, RerunResult
from autoheal.runner.executor import run_command

_FAILING_STATUSES = {"failed", "timedOut", "interrupted"}


class PlaywrightJSAdapter(TestFrameworkAdapter):
    name = "playwright"
    language = "typescript"

    def run_suite(self) -> Path:
        results_path = self.repo_root / "autoheal-results.json"
        npx = shutil.which("npx") or "npx"
        subprocess.run(
            [npx, "playwright", "test", "--reporter=json"],
            cwd=self.repo_root,
            stdout=results_path.open("w", encoding="utf-8"),
            stderr=subprocess.PIPE,
            check=False,
        )
        return results_path

    def parse_results(self, results_path: Path) -> list[FailureReport]:
        data = json.loads(results_path.read_text(encoding="utf-8"))
        # Playwright's `file` fields on suites/specs are relative to `config.rootDir`
        # (i.e. `testDir`), not necessarily the repo root - resolve to repo-relative.
        root_dir = data.get("config", {}).get("rootDir")
        failures: list[FailureReport] = []
        for suite in data.get("suites", []):
            failures.extend(self._walk_suite(suite, ancestor_titles=[], root_dir=root_dir))
        return failures

    def _walk_suite(
        self,
        suite: dict,
        ancestor_titles: list[str],
        root_dir: str | None,
        parent_raw_file: str = "",
    ) -> list[FailureReport]:
        failures: list[FailureReport] = []
        title = suite.get("title", "")
        titles = ancestor_titles + ([title] if title else [])
        raw_file = suite.get("file") or parent_raw_file
        file_path = resolve_repo_relative_path(raw_file, root_dir, self.repo_root)

        for spec in suite.get("specs", []):
            failures.extend(self._spec_failures(spec, titles, file_path))

        for nested in suite.get("suites", []):
            failures.extend(self._walk_suite(nested, titles, root_dir, raw_file))

        return failures

    def _spec_failures(self, spec: dict, ancestor_titles: list[str], file_path: str) -> list[FailureReport]:
        failures: list[FailureReport] = []
        spec_title = spec.get("title", "")
        full_title = " ".join(t for t in [*ancestor_titles, spec_title] if t)
        line = spec.get("line")

        for test in spec.get("tests", []):
            for result in test.get("results", []):
                if result.get("status") not in _FAILING_STATUSES:
                    continue

                error = result.get("error") or {}
                errors = result.get("errors") or []
                message = error.get("message") or (errors[0].get("message") if errors else "") or "Unknown error"
                stack = error.get("stack", "")

                attachments = {
                    a["name"]: a["path"]
                    for a in result.get("attachments", [])
                    if a.get("path")
                }

                failures.append(
                    FailureReport(
                        test_id=f"{file_path}::{full_title}",
                        test_name=full_title,
                        file_path=file_path,
                        framework=self.name,
                        language=self.language,
                        error_message=message,
                        stack_trace=stack,
                        line=line,
                        attachments=attachments,
                    )
                )
                # One failure record per spec is enough for the heal loop.
                return failures

        return failures

    def run_single(self, failure: FailureReport) -> RerunResult:
        return run_command(
            ["npx", "playwright", "test", failure.file_path, "-g", failure.test_name],
            cwd=self.repo_root,
        )
