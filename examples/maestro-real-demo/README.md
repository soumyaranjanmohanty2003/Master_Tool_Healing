# Maestro demo (verified against a real device)

Unlike [`examples/maestro-demo`](../maestro-demo/), which is illustrative only,
this one was actually run end-to-end against a real Android device connected
over USB (`adb`) with a real installed app (the stock Settings app,
`com.android.settings` — no login or account needed, so it's safe to automate).

## What this proved

The main README used to say Maestro support was "unverified end-to-end."
Running it for real surfaced one genuine bug in
[`src/autoheal/adapters/maestro_adapter.py`](../../src/autoheal/adapters/maestro_adapter.py),
now fixed:

- Maestro's actual JUnit output (CLI 2.5.1) puts the failure detail in the
  `<failure>`/`<error>` element's **text content**, not a `message` attribute.
  The adapter only read the attribute, so every real failure was reported to
  the LLM as `"Unknown error"` instead of the actual reason. Fixed to fall
  back to the element's text.

With that fixed, the full pipeline was run for real:

1. **Detect**: `flows/wifi_settings.yaml` deliberately looks for `"WiFi"`, but
   the device's Settings app labels the row `"Wi-Fi"`. `maestro test` fails
   with `Element not found: Text matching regex: WiFi`, and the adapter now
   parses that into a correct `FailureReport`.
2. **Diagnose**: Groq correctly identified the root cause
   (`fix_type=selector_update`, `confidence=high`, *"the test is looking for
   'WiFi' but the actual text on the screen is 'Wi-Fi'"*) and produced the
   correct one-line fix.
3. **Patch + verify**: applying that exact fix (`"WiFi"` → `"Wi-Fi"`) and
   rerunning against the device passes cleanly (`[Passed] wifi_settings`).

Note: in the live `autoheal run`, the rerun-verify step flaked across
multi-minute LLM round-trips because the phone's screen timed out/locked
between attempts, which stalls Maestro's driver connection. That's a device
environment issue (fixed here by raising `screen_off_timeout` via
`adb shell settings put system screen_off_timeout <ms>` and waking the
screen before each run), not a bug in AutoHeal's diagnose/patch logic — the
diagnosis was correct on both attempts where the device stayed awake.

## Reproducing

```bash
adb devices                     # confirm your device shows up
adb shell settings put system screen_off_timeout 1800000   # avoid mid-run lock
adb shell input keyevent KEYCODE_WAKEUP

cd examples/maestro-real-demo
maestro test flows/ --format junit --output autoheal-results.xml   # real failure

cd ../..
export GROQ_API_KEY=...
.venv/Scripts/autoheal run --repo-root examples/maestro-real-demo \
  --framework maestro --results-file examples/maestro-real-demo/autoheal-results.xml \
  --dry-run
```

`--dry-run` patches and reruns locally but never pushes or opens a PR, and
reverts the patch if the rerun still fails.
