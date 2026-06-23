# Trigger Recall Opt-In Read-Only Control Plane

Date: 2026-06-23

## Summary

Implemented the first runtime opt-in slice for trigger-recall baseline acceptance:
two read-only MCP control-plane tools that report status and transition readiness
without calling `memory_search`, changing default ordering, changing schemas, or
enforcing holds.

## Added Surfaces

- `trigger_recall_opt_in_status`
  - Consumes explicit request shape plus redacted regression metrics.
  - Requires explicit per-call opt-in, `mode=fts`, exact `project:/...` local
    scope with `scope_mode=local_only`, `AB_TRIGGER_RECALL_OPT_IN=1`, and no
    operator disable.
  - Reports the baseline-acceptance regression anchor
    `aio2_trigger_recall_baseline_acceptance_shadow_20260623`.
  - Includes only redacted counts, scope hash, gate state, and side-effect
    flags.

- `trigger_recall_opt_in_runtime_transition_gate`
  - Consumes the status packet without echoing it.
  - Allows only the next gated-baseline-trial surface when the status packet and
    requested transition are clean.
  - Keeps `may_enforce_hold=false` and does not approve production retrieval
    changes.

Both tools are registered as `Niche`, so the default tool surface is not widened.

## Boundaries

- No store access.
- No `memory_search` or graph retrieval calls.
- No coactivation recording.
- No default ordering/schema change.
- No hold enforcement.
- No raw query, key, content, or status-packet echo.

## Verification

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 7 passed.
- `cargo check -p ab-bridge --lib`
  - Passed with existing warnings only.
- `git diff --check`
  - Passed.

## Next Gate

The next implementation slice can add `trigger_recall_opt_in_gated_baseline_trial`
behind this transition gate. That slice should still avoid changing default
`memory_search` behavior and should return explicit held-query status rather
than a bare empty result.
