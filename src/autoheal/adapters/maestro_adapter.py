"""Adapter for Maestro (mobile UI testing, YAML flow files).

Results are ingested from Maestro's JUnit XML report, produced via:

    maestro test <flows> --format junit --output report.xml

Each Maestro flow file is normally one test case, so failure granularity here
is per-file rather than per-function - `test_id`/`file_path` both point at the
flow's `.yaml`/`.yml` file, and rerunning means re-running that whole flow.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter, resolve_repo_relative_path
from autoheal.models import FailureReport, RerunResult
from autoheal.runner.executor import run_command

_FLOW_EXTENSIONS = (".yaml", ".yml")


class MaestroAdapter(TestFrameworkAdapter):
    name = "maestro"
    language = "yaml"

    def run_suite(self) -> Path:
        results_path = self.repo_root / "autoheal-results.xml"
        subprocess.run(
            ["maestro", "test", str(self.repo_root), "--format", "junit", "--output", str(results_path)],
            cwd=self.repo_root,
            capture_output=True,
            check=False,
        )
        return results_path

    def parse_results(self, results_path: Path) -> list[FailureReport]:
        tree = ET.parse(results_path)
        root = tree.getroot()
        failures: list[FailureReport] = []

        for testcase in root.iter("testcase"):
            fault_el = testcase.find("failure")
            if fault_el is None:
                fault_el = testcase.find("error")
            if fault_el is None:
                continue

            name = testcase.get("name", "")
            file_path = self._resolve_flow_path(testcase, name)

            # Maestro's real JUnit output (as of CLI 2.5.1) puts the failure
            # detail in the <failure>/<error> element's text content, not a
            # `message` attribute - unlike the JUnit convention this adapter
            # was originally written against. Prefer the attribute if a
            # future Maestro version adds one, but fall back to the text.
            message_attr = (fault_el.get("message") or "").strip()
            text_content = (fault_el.text or "").strip()
            error_message = message_attr or text_content or "Unknown error"
            stack_trace = text_content if text_content != error_message else ""

            failures.append(
                FailureReport(
                    test_id=file_path or name,
                    test_name=name or file_path,
                    file_path=file_path,
                    framework=self.name,
                    language=self.language,
                    error_message=error_message,
                    stack_trace=stack_trace,
                    # Maestro's JUnit report has no per-step line number; the
                    # context collector falls back to the whole flow file,
                    # which is normally short enough not to need one.
                    line=None,
                )
            )

        return failures

    def _resolve_flow_path(self, testcase: ET.Element, name: str) -> str:
        raw_file = testcase.get("file") or testcase.get("classname", "")
        file_path = resolve_repo_relative_path(raw_file, None, self.repo_root)
        if file_path.endswith(_FLOW_EXTENSIONS) and (self.repo_root / file_path).is_file():
            return file_path
        # `classname` wasn't a usable path (e.g. Maestro reported just the flow's
        # `name:` rather than its file path) - fall back to matching a flow file
        # by name under the repo.
        found = self._find_flow_file(name) or self._find_flow_file(raw_file)
        return found or file_path

    def _find_flow_file(self, stem: str) -> str | None:
        if not stem:
            return None
        for ext in _FLOW_EXTENSIONS:
            for candidate in self.repo_root.rglob(f"*{ext}"):
                if candidate.stem == stem:
                    return candidate.relative_to(self.repo_root).as_posix()
        return None

    def run_single(self, failure: FailureReport) -> RerunResult:
        return run_command(["maestro", "test", failure.file_path], cwd=self.repo_root)
