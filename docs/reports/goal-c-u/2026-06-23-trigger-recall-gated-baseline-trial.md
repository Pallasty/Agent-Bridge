# Trigger Recall Gated Baseline Trial

Date: 2026-06-23

Authorization base: `6d72f8b` (`docs(memory): review trigger opt-in slice1`)

## Summary

Implemented the second trigger-recall runtime opt-in control-plane slice:
`trigger_recall_opt_in_gated_baseline_trial`.

The new surface is a separate transition-gated trial. It does not add a
parameter to default `memory_search`, does not change default retrieval order or
schema, and does not authorize production `enforce_hold`.

## Added Surface

- `trigger_recall_opt_in_gated_baseline_trial`
  - Requires a clean `trigger_recall_opt_in_runtime_transition_gate` packet.
  - Requires `mode=fts`, `per_call_opt_in=true`, exact local project scope, and
    runtime opt-in via `AB_TRIGGER_RECALL_OPT_IN=1`.
  - Refuses to call store FTS when the transition gate is blocked or malformed.
  - Calls store baseline FTS only after the transition gate allows the trial.
  - Runs deterministic query-intent acceptance labels:
    - `write_bypass_intent`
    - `creative_non_continuation_intent`
    - `frontend_dashboard_intent`
    - `health_dashboard_intent`
  - Returns redacted accepted or held status:
    - accepted: `status=returned_accepted`
    - held: `status=held_by_query_intent`
    - blocked: `status=transition_gate_blocked`

## Boundary

- Default `memory_search` remains unchanged.
- The tool does not call the MCP `memory_search` tool.
- The tool does not record coactivation.
- The tool does not write memories or graph edges.
- The tool does not run semantic or graph retrieval.
- The tool does not expose raw query, raw keys, memory content, or scope paths
  in output.
- Held baseline queries return an explicit hold packet, not a bare empty search
  result.

## Verification

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 14 passed.
- `cargo check -p ab-bridge --lib`
  - Passed with existing warnings only.
- `git diff --check`
  - Passed.

## Next Gate

The next safe slice is a redacted batch diagnostic through the gated trial over
the Aio2 trigger corpus positives and negative controls, followed by a review
packet comparing default baseline FTS, gated accepted calls, gated held calls,
and eval-only `union+cont`.
