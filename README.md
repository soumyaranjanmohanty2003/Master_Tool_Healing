# AutoHeal

Self-healing test automation. When a Playwright test fails in CI, AutoHeal uses
an LLM (via [Groq](https://groq.com)) to diagnose the root cause, generate a
fix, verify the fix by rerunning the failing test, and — if it passes — opens a
pull request with the fix. It never touches application/product source, only
the failing test script itself, and every fix lands as a PR for human review.

Currently supports **Playwright** in both JS/TS and Python (pytest-playwright)
flavors. Selenium and Maestro YAML support is planned; the adapter interface
(`autoheal.adapters.base.TestFrameworkAdapter`) is designed to make adding them
a matter of implementing `parse_results` / `run_single`, not touching the rest
of the pipeline.

## How it works

1. **Detect** - parses your test runner's failure output (Playwright's
   `--reporter=json`, or pytest-json-report/JUnit XML) into a normalized
   failure report.
2. **Diagnose** - sends the error, stack trace, and the failing test's source
   to Groq, which returns a root cause and (if it's confident) a full corrected
   version of the file.
3. **Patch** - computes a unified diff from that corrected file, rejects it if
   it touches anything other than the one failing test file or changes too
   many lines, then applies it.
4. **Verify** - reruns *only* the failing test. If it still fails, the patch is
   reverted and the LLM gets another attempt (bounded by `--max-attempts`,
   default 3) with the previous failure as context. If it passes, we proceed.
5. **PR** - commits the fix on a new branch and opens a pull request via the
   GitHub API. Nothing is ever pushed directly to your base branch.

## Usage in GitHub Actions

```yaml
- uses: actions/checkout@v4
- run: npm ci && npx playwright install --with-deps
- name: Run tests
  id: tests
  run: npx playwright test --reporter=json > results.json
  continue-on-error: true
- name: Auto-heal on failure
  if: steps.tests.outcome == 'failure'
  uses: <org>/autoheal@v1
  with:
    results-file: results.json
    groq-api-key: ${{ secrets.GROQ_API_KEY }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

See [`.github/workflows/demo.yml`](.github/workflows/demo.yml) and
[`examples/`](examples/) for working end-to-end examples in both JS/TS and
Python, each with one deliberately brittle test.

## Local usage

```
pip install -e ".[dev]"
export GROQ_API_KEY=...
autoheal run --repo-root path/to/your/repo --results-file results.json --dry-run
```

`--dry-run` runs the full diagnose/patch/rerun loop without pushing or opening
a PR - useful for testing against a real failure locally.

## Safety model

- A generated patch may only modify the single file the failing test lives in.
  Diffs touching any other file are rejected outright.
- Diffs beyond `--max-changed-lines` (default 200) are rejected.
- If the LLM isn't confident the failure is a test-script issue (as opposed to
  a real product regression), it returns `no_fix_possible` and AutoHeal reports
  the diagnosis without attempting a fix.
- Fixes only ever land via a PR; nothing is committed to your base branch
  directly.
- Error messages, stack traces, and source snippets are redacted (API keys,
  bearer tokens, JWTs, AWS keys, credentials in URLs) before being sent to Groq.

## Development

```
pip install -e ".[dev]"
pytest
```
