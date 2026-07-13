# Maestro demo (illustrative)

Unlike the Playwright JS/Python demos in this repo, this one **can't run
standalone** — Maestro drives a real installed app on a device or emulator,
so `flows/login.yaml` targets a fictitious `com.example.demoapp` that doesn't
exist. There's no Maestro CLI or mobile emulator available in the environment
this project was built in, so the Maestro adapter has **not** been verified
against a real `maestro test` run the way the Playwright adapters were
(see the main [README](../../README.md)) — it's implemented from Maestro's
documented JUnit output conventions.

This exists to document the expected wiring. To actually try it:

1. Point `appId` in `flows/login.yaml` at a real app you have installed on a
   device/emulator, and change the flow's steps to match a real screen in
   that app (with the same kind of deliberately-stale selector).
2. Generate a JUnit report:
   ```bash
   maestro test flows/ --format junit --output autoheal-results.xml
   ```
3. Run AutoHeal against it:
   ```bash
   autoheal run --repo-root . --framework maestro --results-file autoheal-results.xml --dry-run
   ```
4. Please report back (via an issue or to whoever maintains this fork) if
   Maestro's actual JUnit field names differ from what
   `src/autoheal/adapters/maestro_adapter.py` expects — the parsing logic may
   need small adjustments based on your real report's structure.

## CI wiring (once you have a device/emulator step in your workflow)

```yaml
- name: Run Maestro flows
  id: tests
  run: maestro test flows/ --format junit --output autoheal-results.xml
  continue-on-error: true

- name: Auto-heal
  if: steps.tests.outcome == 'failure'
  uses: <org>/autoheal@v1
  with:
    framework: maestro
    results-file: autoheal-results.xml
    groq-api-key: ${{ secrets.GROQ_API_KEY }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

This isn't wired into [`.github/workflows/demo.yml`](../../.github/workflows/demo.yml)
because it would fail on every run without real device/emulator infrastructure
in place.
