# Trigger Recall Opt-In Slice 1 Batch Matrix Review - 2026-06-23

Host: macOS `maxiaodeMac-Pro.local`

Review base: `7fb2fea` (`feat(memory): add trigger recall gated baseline trial`)

Scope: test hardening and acceptance review for the Slice 1 read-only
trigger-recall opt-in status/transition gate after Slice 2 has landed. This
review does not authorize a default `memory_search` behavior change, hidden
`memory_search` parameter, coactivation change, memory write, graph write,
reindex, or production hold enforcement.

## Verdict

`ACCEPTED-SLICE-1-AS-READONLY-GATE-WITH-BATCH-MATRIX`.

The implemented Slice 1 surfaces remain acceptable as the precondition for the
Slice 2 gated baseline trial:

- `trigger_recall_opt_in_status`
- `trigger_recall_opt_in_runtime_transition_gate`

This review adds executable batch coverage for the status/gate blocking matrix.
The transition gate may report `may_call_gated_baseline_trial=true` only when
the status packet and requested transition are clean, redacted, read-only,
exact-scope, `fts`-only, per-call opted in, runtime-enabled, operator-enabled,
and backed by the expected regression anchor.

Because GitHub has already advanced through `6d72f8b` and `7fb2fea`, this report
does not re-open whether a single-call gated baseline trial may exist. It
narrows the next required step: run and review redacted batch diagnostics for
that gated trial before considering any production-visible hold behavior.

| Item | State |
|---|---|
| default `memory_search` behavior | `NO-GO` |
| hidden parameter on `memory_search` | `NO-GO` |
| read-only status surface | `ACCEPTED` |
| read-only runtime transition gate | `ACCEPTED-WITH-BATCH-MATRIX` |
| gated baseline trial surface | `LANDED-IN-7fb2fea` |
| gated baseline batch diagnostic | `NEXT-REVIEW-POINT` |
| `enforce_hold` visible behavior | `NO-GO` |
| supplemental projected candidate trial | `OUT-OF-SCOPE` |

## Board And Repo Verification

- Thread #120 post #3973 recorded the Slice 1 merge/reconcile closeout.
- Thread #120 post #3974 is a separate multilingual embedder probe lane. It left
  `crates/store/examples/zh_embed_probe.rs` untracked; this review intentionally
  does not touch or stage that file.
- `6d72f8b` added the Slice 1 post-implementation review and approved only the
  constrained Slice 2 single-call implementation.
- `7fb2fea` added `trigger_recall_opt_in_gated_baseline_trial` as a separate
  transition-gated diagnostic surface.

## Reviewed Implementation

Code:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`

Reports:

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-slice1-post-implementation-review.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-gated-baseline-trial.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-production-optin-review.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-optin-readonly-control-plane.md`

## Added Batch Matrix

The pure builder tests now cover the following status blockers:

| Case | Expected blocker |
|---|---|
| non-`fts` mode | `requested_mode_not_authorized` |
| missing per-call opt-in | `per_call_opt_in_missing` |
| non-exact project scope | `exact_local_project_scope_missing` |
| operator disabled | `operator_disabled` |
| missing required metric | `eval_metrics_absent` |
| lost baseline hit metric absent/failing | `baseline_shadow_true_hits_lost` |
| union continuation miss | `union_cont_misses_present` |
| stale regression anchor | `regression_anchor_mismatch` |
| raw payload marker | `raw_payload_fields_present` |

The transition gate tests now cover:

| Case | Expected result |
|---|---|
| ready redacted status packet | `transition_allowed=true`, `may_call_gated_baseline_trial=true`, `may_enforce_hold=false` |
| status packet not ready | blocks with `status_packet_not_ready_for_transition_gate` and source-prefixed blocker |
| status schema mismatch | blocks with `status_packet_schema_mismatch` |
| status side-effect contract polluted | blocks with `status_packet_side_effect_contract_invalid` |
| gate request non-`fts` | blocks with `requested_mode_not_authorized` |
| gate request missing per-call opt-in | blocks with `per_call_opt_in_missing` |
| gate request raw payload marker | blocks with `raw_payload_fields_present` |
| raw status packet | blocks with `status_packet_contains_raw_payload` without echoing raw query text |

These checks protect the Slice 2 trial from being called through a permissive or
polluted transition packet.

## Verification

Current verification for this batch-matrix slice:

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 17 passed after merge with `7fb2fea`.
- `cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture`
  - 27 passed after merge with `7fb2fea`.
- `cargo check -p ab-bridge --examples`
  - Passed with existing warnings only.

Existing warnings observed:

- `ab-store` mixed-script confusable warning for the existing beta-named test.
- `ab-bridge` private-interface warning for `ToolPolicy`.
- Existing unused Option E helpers and related helper functions in
  `crates/bridge/src/mcp_tools.rs`.

## Remaining Risk

Slice 1 still consumes redacted readiness metrics supplied by the caller; it does
not independently prove that every later store-search call is safe. Slice 2 can
now perform a transition-gated single-call trial, but it still needs redacted
batch diagnostics across positive and negative controls before any production
visible hold behavior can be discussed.

Next review packet should compare:

- default baseline FTS;
- gated accepted calls;
- gated held calls;
- eval-only `union+cont`;
- query hashes and order hashes only, no raw query/key/content leakage;
- coactivation and default-search side effects remain absent.

## Decision

Proceed next to the gated baseline batch diagnostic/review packet. Do not
implement `enforce_hold` and do not modify default `memory_search`.
