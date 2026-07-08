"""Picks the right Playwright flavor (JS/TS vs Python) for a repo."""

from __future__ import annotations

import json
from pathlib import Path

from autoheal.adapters.base import TestFrameworkAdapter
from autoheal.adapters.playwright_js_adapter import PlaywrightJSAdapter
from autoheal.adapters.playwright_python_adapter import PlaywrightPythonAdapter


def detect_adapter(repo_root: Path, results_file: str | None = None) -> TestFrameworkAdapter:
    if results_file:
        by_results = _from_results_file(Path(results_file))
        if by_results is not None:
            return by_results(repo_root)

    by_repo = _from_repo_contents(repo_root)
    if by_repo is not None:
        return by_repo(repo_root)

    raise ValueError(
        f"Could not detect whether {repo_root} uses Playwright JS/TS or "
        "Playwright Python (pytest-playwright). Pass --framework-language explicitly."
    )


def _from_results_file(path: Path):
    if not path.is_file():
        return None
    if path.suffix == ".xml":
        return PlaywrightPythonAdapter
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


def _from_repo_contents(repo_root: Path):
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
