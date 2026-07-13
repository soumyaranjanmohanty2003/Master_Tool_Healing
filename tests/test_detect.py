from pathlib import Path

import pytest

from autoheal.adapters.detect import detect_adapter
from autoheal.adapters.maestro_adapter import MaestroAdapter
from autoheal.adapters.playwright_js_adapter import PlaywrightJSAdapter
from autoheal.adapters.playwright_python_adapter import PlaywrightPythonAdapter


def test_detects_js_from_config_file(tmp_path: Path):
    (tmp_path / "playwright.config.ts").write_text("export default {}", encoding="utf-8")
    adapter = detect_adapter(tmp_path)
    assert isinstance(adapter, PlaywrightJSAdapter)


def test_detects_js_from_package_json(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"@playwright/test": "^1.47.0"}}', encoding="utf-8"
    )
    adapter = detect_adapter(tmp_path)
    assert isinstance(adapter, PlaywrightJSAdapter)


def test_detects_python_from_requirements(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("pytest-playwright>=0.5.0\n", encoding="utf-8")
    adapter = detect_adapter(tmp_path)
    assert isinstance(adapter, PlaywrightPythonAdapter)


def test_detects_python_from_results_file_extension(tmp_path: Path):
    results = tmp_path / "results.xml"
    results.write_text("<testsuites/>", encoding="utf-8")
    adapter = detect_adapter(tmp_path, results_file=str(results))
    assert isinstance(adapter, PlaywrightPythonAdapter)


def test_raises_when_undetectable(tmp_path: Path):
    with pytest.raises(ValueError):
        detect_adapter(tmp_path)


def test_detects_maestro_from_maestro_dir(tmp_path: Path):
    (tmp_path / ".maestro").mkdir()
    adapter = detect_adapter(tmp_path)
    assert isinstance(adapter, MaestroAdapter)


def test_detects_maestro_from_flow_file_contents(tmp_path: Path):
    flows = tmp_path / "flows"
    flows.mkdir()
    (flows / "login.yaml").write_text("appId: com.example.app\n---\n- launchApp\n", encoding="utf-8")
    adapter = detect_adapter(tmp_path)
    assert isinstance(adapter, MaestroAdapter)


def test_detects_maestro_from_results_file_contents(tmp_path: Path):
    results = tmp_path / "results.xml"
    results.write_text(
        '<testsuites><testsuite><testcase file="flows/login.yaml" name="login"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    adapter = detect_adapter(tmp_path, results_file=str(results))
    assert isinstance(adapter, MaestroAdapter)


def test_framework_override_forces_adapter_regardless_of_repo_contents(tmp_path: Path):
    (tmp_path / "playwright.config.ts").write_text("export default {}", encoding="utf-8")
    adapter = detect_adapter(tmp_path, framework="maestro")
    assert isinstance(adapter, MaestroAdapter)


def test_framework_override_playwright_python(tmp_path: Path):
    adapter = detect_adapter(tmp_path, framework="playwright-python")
    assert isinstance(adapter, PlaywrightPythonAdapter)
