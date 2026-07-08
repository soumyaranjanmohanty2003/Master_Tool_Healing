"""Opens a pull request via the GitHub REST API."""

from __future__ import annotations

import requests

API_ROOT = "https://api.github.com"


class GitHubAPIError(RuntimeError):
    pass


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def open_pull_request(
    *,
    repo: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> str:
    """Creates a PR and (best-effort) applies labels. Returns the PR's HTML URL."""
    resp = requests.post(
        f"{API_ROOT}/repos/{repo}/pulls",
        headers=_headers(token),
        json={"title": title, "head": head_branch, "base": base_branch, "body": body},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise GitHubAPIError(f"Failed to create PR ({resp.status_code}): {resp.text}")

    pr = resp.json()
    pr_number = pr["number"]
    pr_url = pr["html_url"]

    if labels:
        label_resp = requests.post(
            f"{API_ROOT}/repos/{repo}/issues/{pr_number}/labels",
            headers=_headers(token),
            json={"labels": labels},
            timeout=30,
        )
        if label_resp.status_code >= 300:
            # Labels are a nice-to-have; don't fail the whole run over them.
            pass

    return pr_url
