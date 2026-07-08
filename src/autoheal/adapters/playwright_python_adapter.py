"""Adapter for Playwright via pytest (pytest-playwright): the `pytest` runner.

Results are ingested from either `pytest-json-report` output (preferred - richer
tracebacks) or JUnit XML (`pytest --junitxml=...`), selected by the results file's
extension.
"""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter, resolve_repo_relative_path
from autoheal.models import FailureReport, RerunResult
from autoheal.runner.executor import run_command

_FAILING_OUTCOMES = {"failed", "error"}


class PlaywrightPythonAdapter(TestFrameworkAdapter):
    name = "playwright"
    language = "python"

    def run_suite(self) -> Path:
        results_path = self.repo_root / "autoheal-results.json"
        subprocess.run(
            [
                "pytest",
                "--json-report",
                f"--json-report-file={results_path}",
            ],
            cwd=self.repo_root,
            capture_output=True,
            check=False,
        )
        return results_path

    def parse_results(self, results_path: Path) -> list[FailureReport]:
        if results_path.suffix == ".xml":
            return self._parse_junit_xml(results_path)
        return self._parse_json_report(results_path)

    def _parse_json_report(self, results_path: Path) -> list[FailureReport]:
        data = json.loads(results_path.read_text(encoding="utf-8"))
        # pytest computes `nodeid`s relative to its own auto-detected `root`
        # (nearest ancestor with a pyproject.toml/pytest.ini/etc.), which is not
        # necessarily `self.repo_root` - resolve to repo-relative before using.
        pytest_root = data.get("root")
        failures: list[FailureReport] = []

        for test in data.get("tests", []):
            if test.get("outcome") not in _FAILING_OUTCOMES:
                continue

            nodeid = test["nodeid"]
            raw_file, sep, rest = nodeid.partition("::")
            file_path = resolve_repo_relative_path(raw_file, pytest_root, self.repo_root)
            test_id = f"{file_path}{sep}{rest}" if sep else file_path

            call = test.get("call") or test.get("setup") or {}
            crash = call.get("crash") or {}
            message = crash.get("message", "") or "Unknown error"
            longrepr = call.get("longrepr", "")

            failures.append(
                FailureReport(
                    test_id=test_id,
                    test_name=rest or nodeid,
                    file_path=file_path,
                    framework=self.name,
                    language=self.language,
                    error_message=message,
                    stack_trace=longrepr if isinstance(longrepr, str) else json.dumps(longrepr),
                    line=self._extract_line(test, call, file_path),
                )
            )

        return failures

    def _extract_line(self, test: dict, call: dict, file_path: str) -> int | None:
        # `call.crash.lineno` points at the *innermost* traceback frame, which
        # is usually deep inside a library (e.g. Playwright's own internals),
        # not the test file. Prefer the traceback frame that's actually in the
        # test file; it's 1-indexed already, unlike the top-level `lineno`.
        target = (self.repo_root / file_path).resolve() if file_path else None
        for frame in call.get("traceback") or []:
            frame_path = frame.get("path")
            if not frame_path or target is None:
                continue
            try:
                if (self.repo_root / frame_path).resolve() == target:
                    return frame.get("lineno")
            except OSError:
                continue

        top_lineno = test.get("lineno")
        return top_lineno + 1 if isinstance(top_lineno, int) else None

    def _parse_junit_xml(self, results_path: Path) -> list[FailureReport]:
        tree = ET.parse(results_path)
        root = tree.getroot()
        failures: list[FailureReport] = []

        for testcase in root.iter("testcase"):
            failure_el = testcase.find("failure")
            error_el = testcase.find("error")
            fault_el = failure_el if failure_el is not None else error_el
            if fault_el is None:
                continue

            name = testcase.get("name", "")
            file_path = testcase.get("file") or _classname_to_path(testcase.get("classname", ""))
            line = testcase.get("line")

            failures.append(
                FailureReport(
                    test_id=f"{file_path}::{name}",
                    test_name=name,
                    file_path=file_path,
                    framework=self.name,
                    language=self.language,
                    error_message=fault_el.get("message", "") or "Unknown error",
                    stack_trace=fault_el.text or "",
                    line=int(line) if line else None,
                )
            )

        return failures

    def run_single(self, failure: FailureReport) -> RerunResult:
        return run_command(["pytest", failure.test_id], cwd=self.repo_root)


def _classname_to_path(classname: str) -> str:
    if not classname:
        return ""
    return classname.replace(".", "/") + ".py"
