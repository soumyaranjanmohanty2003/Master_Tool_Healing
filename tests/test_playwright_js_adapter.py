import json
from pathlib import Path

from autoheal.adapters.playwright_js_adapter import PlaywrightJSAdapter


def _sample_results(root_dir: str) -> dict:
    # Mirrors real `playwright test --reporter=json` output: suite/spec `file`
    # fields are relative to `config.rootDir` (the configured testDir), not
    # necessarily the repo root.
    return {
        "config": {"rootDir": root_dir},
        "suites": [
            {
                "title": "example.spec.ts",
                "file": "example.spec.ts",
                "specs": [],
                "suites": [
                    {
                        "title": "sign in flow",
                        "file": "example.spec.ts",
                        "specs": [
                            {
                                "title": "user can sign in",
                                "line": 5,
                                "tests": [
                                    {
                                        "results": [
                                            {
                                                "status": "failed",
                                                "error": {
                                                    "message": "Timeout waiting for selector text=Log In",
                                                    "stack": "Error: Timeout\n at foo.ts:5:1",
                                                },
                                                "attachments": [
                                                    {
                                                        "name": "screenshot",
                                                        "path": "/tmp/shot.png",
                                                        "contentType": "image/png",
                                                    }
                                                ],
                                            }
                                        ]
                                    }
                                ],
                            },
                            {
                                "title": "user can sign out",
                                "line": 20,
                                "tests": [{"results": [{"status": "passed"}]}],
                            },
                        ],
                        "suites": [],
                    }
                ],
            }
        ],
    }


def test_parse_results_extracts_only_failures(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps(_sample_results(str(tests_dir))), encoding="utf-8")

    adapter = PlaywrightJSAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.test_name == "example.spec.ts sign in flow user can sign in"
    assert failure.file_path == "tests/example.spec.ts"
    assert failure.line == 5
    assert "Timeout waiting for selector" in failure.error_message
    assert failure.attachments["screenshot"] == "/tmp/shot.png"
    assert failure.language == "typescript"


def test_run_single_invokes_playwright_with_grep(tmp_path: Path, monkeypatch):
    from autoheal.adapters import playwright_js_adapter as mod

    captured = {}

    def fake_run_command(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        from autoheal.models import RerunResult

        return RerunResult(passed=True, output="ok")

    monkeypatch.setattr(mod, "run_command", fake_run_command)

    adapter = PlaywrightJSAdapter(tmp_path)
    from autoheal.models import FailureReport

    failure = FailureReport(
        test_id="tests/example.spec.ts::user can sign in",
        test_name="user can sign in",
        file_path="tests/example.spec.ts",
        framework="playwright",
        language="typescript",
        error_message="boom",
    )
    result = adapter.run_single(failure)

    assert result.passed is True
    assert captured["cmd"] == ["npx", "playwright", "test", "tests/example.spec.ts", "-g", "user can sign in"]
    assert captured["cwd"] == tmp_path
