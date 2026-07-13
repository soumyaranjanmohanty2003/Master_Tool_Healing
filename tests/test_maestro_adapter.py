from pathlib import Path

from autoheal.adapters.maestro_adapter import MaestroAdapter

JUNIT_BY_FILE_ATTR = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="Maestro">
    <testcase classname="flows.login" name="login flow" file="flows/login.yaml" time="4.2">
      <failure message="Element not found: Log In">Timed out waiting for element</failure>
    </testcase>
    <testcase classname="flows.signup" name="signup flow" file="flows/signup.yaml" time="3.1"/>
  </testsuite>
</testsuites>
"""

JUNIT_BY_NAME_ONLY = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="Maestro">
    <testcase classname="Maestro" name="login" time="4.2">
      <failure message="Element not found: Log In">Timed out waiting for element</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

# Matches Maestro CLI 2.5.1's real `--format junit` output (confirmed against
# a real device run): no `message` attribute, no `file`/per-flow classname -
# the failure text lives in the element body and the file has to be found by
# matching the testcase `name` against a flow file's stem.
JUNIT_REAL_DEVICE_FORMAT = """<?xml version='1.0' encoding='UTF-8'?>
<testsuites>
  <testsuite name="Test Suite" device="ABC123" tests="1" failures="1" time="23.0">
    <testcase id="wifi_settings" name="wifi_settings" classname="wifi_settings" time="23.0" status="ERROR">
      <failure>Element not found: Text matching regex: WiFi</failure>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_parse_results_uses_file_attribute_when_present(tmp_path: Path):
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir()
    (flows_dir / "login.yaml").write_text("appId: com.example\n---\n- tapOn: Log In\n", encoding="utf-8")

    results_file = tmp_path / "results.xml"
    results_file.write_text(JUNIT_BY_FILE_ATTR, encoding="utf-8")

    adapter = MaestroAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.file_path == "flows/login.yaml"
    assert failure.test_id == "flows/login.yaml"
    assert failure.test_name == "login flow"
    assert failure.error_message == "Element not found: Log In"
    assert failure.framework == "maestro"
    assert failure.language == "yaml"


def test_parse_results_falls_back_to_matching_flow_file_by_name(tmp_path: Path):
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir()
    (flows_dir / "login.yaml").write_text("appId: com.example\n---\n- tapOn: Log In\n", encoding="utf-8")

    results_file = tmp_path / "results.xml"
    results_file.write_text(JUNIT_BY_NAME_ONLY, encoding="utf-8")

    adapter = MaestroAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    assert failures[0].file_path == "flows/login.yaml"


def test_parse_results_reads_message_from_element_text_on_real_format(tmp_path: Path):
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir()
    (flows_dir / "wifi_settings.yaml").write_text(
        "appId: com.android.settings\n---\n- tapOn: WiFi\n", encoding="utf-8"
    )

    results_file = tmp_path / "results.xml"
    results_file.write_text(JUNIT_REAL_DEVICE_FORMAT, encoding="utf-8")

    adapter = MaestroAdapter(tmp_path)
    failures = adapter.parse_results(results_file)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.file_path == "flows/wifi_settings.yaml"
    assert failure.error_message == "Element not found: Text matching regex: WiFi"


def test_run_single_invokes_maestro_test(tmp_path: Path, monkeypatch):
    from autoheal.adapters import maestro_adapter as mod
    from autoheal.models import FailureReport, RerunResult

    captured = {}

    def fake_run_command(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return RerunResult(passed=True, output="ok")

    monkeypatch.setattr(mod, "run_command", fake_run_command)

    adapter = MaestroAdapter(tmp_path)
    failure = FailureReport(
        test_id="flows/login.yaml",
        test_name="login flow",
        file_path="flows/login.yaml",
        framework="maestro",
        language="yaml",
        error_message="boom",
    )
    result = adapter.run_single(failure)

    assert result.passed is True
    assert captured["cmd"] == ["maestro", "test", "flows/login.yaml"]
    assert captured["cwd"] == tmp_path
