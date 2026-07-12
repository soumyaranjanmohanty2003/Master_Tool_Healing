"""Configuration loading: defaults < autoheal.yml < environment < CLI args."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_CHANGED_LINES = 200


@dataclass
class AutoHealConfig:
    repo_root: Path = field(default_factory=Path.cwd)
    framework: str = "auto"
    """"auto" to detect Playwright JS/TS vs Python vs Maestro, or an explicit
    "playwright-js" / "playwright-python" / "maestro" to force one."""
    test_command: str | None = None
    """Command that runs the full suite, if a results file isn't already produced."""
    results_file: str | None = None
    """Path to an already-generated results file (Playwright JSON reporter output,
    or a pytest-json-report/JUnit XML file), if the caller ran tests themselves."""

    groq_api_key: str = ""
    groq_model: str = DEFAULT_MODEL

    github_token: str = ""
    github_repo: str = ""
    """"owner/repo", e.g. from GITHUB_REPOSITORY."""
    base_branch: str = "main"
    pr_labels: list[str] = field(default_factory=lambda: ["autoheal"])

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_changed_lines: int = DEFAULT_MAX_CHANGED_LINES
    dry_run: bool = False

    @classmethod
    def load(cls, *, config_path: Path | None = None, overrides: dict | None = None) -> "AutoHealConfig":
        data: dict = {}

        yaml_path = config_path or Path.cwd() / "autoheal.yml"
        if yaml_path.is_file():
            loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            data.update(loaded)

        env_map = {
            "groq_api_key": "GROQ_API_KEY",
            "github_token": "GITHUB_TOKEN",
            "github_repo": "GITHUB_REPOSITORY",
        }
        for field_name, env_var in env_map.items():
            if os.environ.get(env_var):
                data[field_name] = os.environ[env_var]

        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})

        if "repo_root" in data:
            data["repo_root"] = Path(data["repo_root"])

        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
