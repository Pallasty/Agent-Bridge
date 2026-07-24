# R36 — Bounded C2C-B Derivation Probe

Status: **CORE-PATH PASS / FIXTURE-EXIT FOLLOW-UP**

R35 bounds observation-side Keychain derivation to 250 ms. After its completed
source tests and feature build, execute the existing live-lab command exactly
once with fresh disposable custody. Accept only a normal `session_curate`
response with core `saved_count > 0`; the observation receipt may be incomplete
because its sidecar is intentionally fail-closed. Record one result, do not
retry, merge, deploy, enumerate Keychain, or access existing items.

## Attempt-1 receipt

The one run ended at the driver's process deadline with:

```text
after_curate_response_before_exit; last_checkpoint=curate_response_ready
```

This is a positive core-path result: the child emitted the `session_curate`
response after the bounded sidecar path. The residual timeout is fixture-only:
an MCP server remains available after replying, while the driver incorrectly
requires process exit before parsing that reply. This attempt is not retried.
