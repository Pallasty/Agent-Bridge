# Trigger Recall Gated Batch Diagnostics

Date: 2026-06-23

## Summary

Implemented `trigger_recall_opt_in_gated_batch_diagnostics`, a read-only
aggregation surface for redacted `trigger_recall_opt_in_gated_baseline_trial`
packets.

This follows the latest master state where the single-call gated baseline trial
already exists. The new surface does not call store FTS itself. It consumes trial
packets and reports status counts, candidate totals, order-hash counts, hashed
case ids, and blocker summaries.

## Added Surface

- `trigger_recall_opt_in_gated_batch_diagnostics`
  - Registered as `Niche`.
  - Required input: `trial_packets[]`.
  - Each packet includes:
    - `trial_packet`
    - optional `case_id` (output hash only)
    - optional `expected_status`
    - optional `expected_visible_behavior`
  - Output excludes raw trial packets and visible hits.
  - Raw query/key/content fields are rejected and never echoed.

## Boundary

- No store access in the batch tool.
- No `memory_search` call by the batch tool.
- No graph retrieval.
- No coactivation recording.
- No memory or graph writes.
- No default `memory_search` schema/order change.
- No production retrieval default change.
- No `enforce_hold` implementation path.

The tool may report how many supplied trial packets called store FTS, but that
is historical evidence from the trial packets, not a side effect of the batch
tool.

## Decision Semantics

The batch surface can return `ready_for_enforce_hold_review_packet` only when:

- at least one packet is `returned_accepted`;
- at least one packet is `held_by_query_intent`;
- at least one packet is `transition_gate_blocked`;
- no raw query/key/content fields are present;
- expected statuses and visible behaviors match observed trial packets;
- supplied trial packets preserve read-only and no-production-mutation side
  effect contracts.

Even in that state, it reports `may_implement_enforce_hold_now=false` and
`may_change_default_memory_search_now=false`. The only authorized next step is a
review packet before any `enforce_hold` design or runtime behavior.

## Verification

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 21 passed.
- `cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture`
  - 27 passed.
- `cargo check -p ab-bridge --examples`
  - Passed.
- `git diff --check`
  - Passed.

Existing warnings observed:

- `ab-store` mixed-script confusable warning for the existing beta-named test.
- `ab-bridge` private-interface warning for `ToolPolicy`.
- Existing unused Option E helpers and related helper functions in
  `crates/bridge/src/mcp_tools.rs`.

## Local Sync Verification

After fast-forwarding to `ee48804`, Codex reran the trigger slice verification
locally on 2026-06-23:

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 21 passed.
- `cargo check -p ab-bridge --lib`
  - Passed with existing warnings only.
- `cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit`
  - Active rows: 457; trigger rows: 29; projected rows: 28.
  - Corpus: 14 cases; negative controls: 8.
  - Baseline FTS and baseline shadow both remain R@10 0.857, MRR 0.786.
  - True hits lost by shadow gate: 0.
  - Positive cases held: 0.
  - Baseline false hits before shadow gate: 21; after shadow gate: 0.
  - Held controls by reason: creative_non_continuation_intent=2,
    frontend_dashboard_intent=2, health_dashboard_intent=1,
    write_bypass_intent=2.
  - Decision remains eval-only: production `memory_search`, ranking, schema,
    indexing, graph, semantic retrieval, MCP surfaces, and memory rows are
    unchanged by the audit.

## Next Gate

Use the new surface to summarize a redacted accepted/held/blocked trial batch.
If it returns `ready_for_enforce_hold_review_packet`, write a board-visible
review packet comparing default baseline FTS, accepted trial calls, held trial
calls, and transition-blocked controls.

Do not implement `enforce_hold` and do not modify default `memory_search`.
