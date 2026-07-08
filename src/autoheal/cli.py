"""`autoheal run` — CLI entrypoint."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from autoheal.config import AutoHealConfig
from autoheal.orchestrator import heal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoheal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Diagnose, fix, verify, and PR failing tests")
    run.add_argument("--repo-root", default=".", help="Path to the repo under test")
    run.add_argument("--results-file", help="Pre-generated results file (JSON/XML)")
    run.add_argument("--test-command", help="Command to run the full suite if no results file is given")
    run.add_argument("--groq-api-key", help="Overrides GROQ_API_KEY env var")
    run.add_argument("--groq-model", help="Overrides the default Groq model")
    run.add_argument("--github-token", help="Overrides GITHUB_TOKEN env var")
    run.add_argument("--github-repo", help="owner/repo, overrides GITHUB_REPOSITORY env var")
    run.add_argument("--base-branch", default="main")
    run.add_argument("--max-attempts", type=int, default=3)
    run.add_argument("--max-changed-lines", type=int, default=200)
    run.add_argument("--dry-run", action="store_true", help="Diagnose/patch/rerun but never push or open a PR")

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_parser().parse_args(argv)

    if args.command != "run":
        return 1

    config = AutoHealConfig.load(
        overrides={
            "repo_root": Path(args.repo_root).resolve(),
            "results_file": args.results_file,
            "test_command": args.test_command,
            "groq_api_key": args.groq_api_key,
            "groq_model": args.groq_model,
            "github_token": args.github_token,
            "github_repo": args.github_repo,
            "base_branch": args.base_branch,
            "max_attempts": args.max_attempts,
            "max_changed_lines": args.max_changed_lines,
            "dry_run": args.dry_run,
        }
    )

    results = heal(config)

    unhealed = [r for r in results if not r.healed]
    for r in results:
        status = "HEALED" if r.healed else "UNRESOLVED"
        pr_note = f" -> {r.pr_url}" if r.pr_url else ""
        print(f"[{status}] {r.failure.test_name}: {r.summary}{pr_note}")

    return 1 if unhealed else 0


if __name__ == "__main__":
    sys.exit(main())
