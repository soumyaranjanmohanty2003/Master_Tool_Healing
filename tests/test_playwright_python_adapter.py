import json
from pathlib import Path

from autoheal.adapters.playwright_python_adapter import PlaywrightPythonAdapter

def _json_report(root: str) -> dict:
    return {
        "root": root,
        "tests": [
            {
                "nodeid": "tests/test_example.py::test_user_can_sign_in",
                "outcome": "failed",
                "lineno": 6,
                "call": {
                    "outcome": "failed",
                    # `crash` points deep into a library, not the test file -
                    # the adapter must prefer the traceback frame that's
                    # actually in the test file (lineno 15) over this.
                    "crash": {
                        "path": ".venv/site-packages/playwright/_impl/_connection.py",
                        "lineno": 563,
                        "message": "Timeout 30000ms exceeded.",
                    },
                    "traceback": [
                        {"path": "tests/test_example.py", "lineno": 15, "message": ""},
                        {"path": ".venv/site-packages/playwright/_impl/_connection.py", "lineno": 563, "message": "TimeoutError"},
                    ],
                    "longrepr": "Traceback...\nTimeoutError",
                },
            },
            {
                "nodeid": "tests/test_example.py::test_user_can_sign_out",
                "outcome": "passed",
            },
        ],
    }

JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest">
    <testcase classname="tests.test_example" name="test_user_can_sign_in" file="tests/test_example.py" line="6">
      <failure message="Timeout 30000ms exceeded.">Traceback...</failure>
    </testcase>
    <testcase classname="tests.test_example" name="test_user_can_sign_out" file="tests/test_example.py" line="20"/>
  </testsuite>
</testsuites>
"""


def test_parse_json_report(tmp_path: Path):
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps(_json_report(str(tmp_path))), encoding="utf-8")

    adapter = PlaywrightPythonAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.test_id == "tests/test_example.py::test_user_can_sign_in"
    assert failure.test_name == "test_user_can_sign_in"
    assert failure.file_path == "tests/test_example.py"
    assert failure.error_message == "Timeout 30000ms exceeded."
    assert failure.line == 15  # from the traceback frame in the test file, not crash.lineno
    assert failure.language == "python"


def test_parse_json_report_resolves_nodeid_relative_to_pytest_root(tmp_path: Path):
    # pytest's auto-detected `root` can differ from the repo root the adapter
    # was given (e.g. an ancestor directory with its own pyproject.toml).
    outer_root = tmp_path.parent
    report = _json_report(str(outer_root))
    rel_to_outer = tmp_path.name + "/tests/test_example.py"
    report["tests"][0]["nodeid"] = f"{rel_to_outer}::test_user_can_sign_in"
    report["tests"][0]["call"]["traceback"][0]["path"] = "tests/test_example.py"

    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps(report), encoding="utf-8")

    adapter = PlaywrightPythonAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.file_path == "tests/test_example.py"
    assert failure.test_id == "tests/test_example.py::test_user_can_sign_in"


def test_parse_junit_xml(tmp_path: Path):
    results_file = tmp_path / "results.xml"
    results_file.write_text(JUNIT_XML, encoding="utf-8")

    adapter = PlaywrightPythonAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.test_id == "tests/test_example.py::test_user_can_sign_in"
    assert failure.error_message == "Timeout 30000ms exceeded."
    assert failure.line == 6


def test_run_single_invokes_pytest_with_nodeid(tmp_path: Path, monkeypatch):
    from autoheal.adapters import playwright_python_adapter as mod

    captured = {}

    def fake_run_command(cmd, cwd):
        captured["cmd"] = cmd
        from autoheal.models import RerunResult

        return RerunResult(passed=False, output="fail")

    monkeypatch.setattr(mod, "run_command", fake_run_command)

    adapter = PlaywrightPythonAdapter(tmp_path)
    from autoheal.models import FailureReport

    failure = FailureReport(
        test_id="tests/test_example.py::test_user_can_sign_in",
        test_name="test_user_can_sign_in",
        file_path="tests/test_example.py",
        framework="playwright",
        language="python",
        error_message="boom",
    )
    result = adapter.run_single(failure)

    assert result.passed is False
    assert captured["cmd"] == ["pytest", "tests/test_example.py::test_user_can_sign_in"]
