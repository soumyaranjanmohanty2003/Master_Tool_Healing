"""Picks the right adapter (Playwright JS/TS, Playwright Python, or Maestro)
for a repo, or honors an explicit override.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter
from autoheal.adapters.maestro_adapter import MaestroAdapter
from autoheal.adapters.playwright_js_adapter import PlaywrightJSAdapter
from autoheal.adapters.playwright_python_adapter import PlaywrightPythonAdapter

_EXPLICIT = {
    "playwright-js": PlaywrightJSAdapter,
    "playwright-python": PlaywrightPythonAdapter,
    "maestro": MaestroAdapter,
}


def detect_adapter(
    repo_root: Path,
    results_file: str | None = None,
    framework: str | None = None,
) -> TestFrameworkAdapter:
    framework = (framework or "auto").lower()
    if framework in _EXPLICIT:
        return _EXPLICIT[framework](repo_root)

    if results_file:
        by_results = _from_results_file(Path(results_file))
        if by_results is not None:
            return by_results(repo_root)

    by_repo = _from_repo_contents(repo_root)
    if by_repo is not None:
        return by_repo(repo_root)

    raise ValueError(
        f"Could not detect a supported framework for {repo_root} (tried "
        "Playwright JS/TS, Playwright Python, and Maestro). Pass --framework "
        "explicitly (playwright-js, playwright-python, or maestro)."
    )


def _from_results_file(path: Path):
    if not path.is_file():
        return None

    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if "suites" in data and "config" in data:
            return PlaywrightJSAdapter
        if "tests" in data:
            return PlaywrightPythonAdapter
        return None

    if path.suffix == ".xml":
        return _sniff_junit_flavor(path)

    return None


def _sniff_junit_flavor(path: Path):
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None
    root = tree.getroot()

    attr_values = []
    for el in root.iter():
        attr_values.extend(el.attrib.values())
    joined = " ".join(attr_values)

    if ".yaml" in joined or ".yml" in joined:
        return MaestroAdapter
    # Default assumption for JUnit XML we can't otherwise identify: pytest
    # (dotted `classname`s, no file extension in the class/name attributes).
    return PlaywrightPythonAdapter


def _from_repo_contents(repo_root: Path):
    if _looks_like_maestro(repo_root):
        return MaestroAdapter

    if any((repo_root / name).exists() for name in ("playwright.config.ts", "playwright.config.js")):
        return PlaywrightJSAdapter

    package_json = repo_root / "package.json"
    if package_json.is_file():
        try:
            pkg = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pkg = {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "@playwright/test" in deps:
            return PlaywrightJSAdapter

    for req_file in ("requirements.txt", "requirements-dev.txt", "pyproject.toml"):
        candidate = repo_root / req_file
        if candidate.is_file() and "pytest-playwright" in candidate.read_text(encoding="utf-8"):
            return PlaywrightPythonAdapter

    if (repo_root / "conftest.py").exists() or (repo_root / "pytest.ini").exists():
        return PlaywrightPythonAdapter

    return None


def _looks_like_maestro(repo_root: Path) -> bool:
    if (repo_root / ".maestro").is_dir():
        return True

    checked = 0
    for ext in ("*.yaml", "*.yml"):
        for candidate in repo_root.rglob(ext):
            checked += 1
            if checked > 200:  # avoid scanning huge repos file-by-file
                return False
            try:
                head = candidate.read_text(encoding="utf-8", errors="ignore")[:512]
            except OSError:
                continue
            if "appId:" in head:
                return True
    return False
