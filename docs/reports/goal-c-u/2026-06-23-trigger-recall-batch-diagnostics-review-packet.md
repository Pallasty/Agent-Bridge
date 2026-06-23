# Trigger Recall Batch Diagnostics Review Packet

Date: 2026-06-23

Scope: read-only review packet for the post-Slice-2 trigger-recall gate. This
report does not change default `memory_search`, does not authorize production
`enforce_hold`, does not deploy, and does not write memory or graph edges.

## Verdict

`APPROVED-AS-REVIEW-EVIDENCE`.

The committed redacted batch diagnostics surface is sufficient to summarize
accepted, held, and blocked gated-trial packets alongside the current baseline
and eval-only `union+cont` evidence, without exposing raw queries, keys,
content, local paths, visible hit bodies, or transition-gate payloads.

It is not sufficient to enable production visible hold behavior. `enforce_hold`
remains `NO-GO`.

## Evidence Matrix

| Surface | Current Evidence | Boundary |
|---|---:|---|
| Default baseline FTS | Current audit: R@10 0.857, MRR 0.786 | Unchanged production behavior |
| Baseline shadow gate | Current audit: true hits lost 0, positive cases held 0 | Eval/read-only evidence only |
| Gated accepted calls | Batch consumes redacted accepted trial packets | Trial packets must already come from explicit transition gate + per-call opt-in |
| Gated held calls | Batch consumes redacted held trial packets with reasons | Held packet, not empty search |
| Negative controls | Current audit: baseline false hits 21 before gate, 0 after shadow gate | Evidence only; no default suppression |
| Eval-only `union+cont` | Prior aio2-native eval: R@10 1.000, false hits 0 | Separate projected-union experiment, not production authority |

## Batch Surface Contract

`trigger_recall_opt_in_gated_batch_diagnostics`:

- consumes redacted `trigger_recall_opt_in_gated_baseline_trial` packets;
- returns hashes, counts, status buckets, baseline order hashes, and hold
  reasons;
- does not echo raw queries, case ids, memory keys, memory content, visible hit
  bodies, scope paths, or the transition-gate packet;
- does not call store FTS itself;
- does not call the MCP `memory_search` tool;
- does not record coactivation or access traces;
- does not write memories or graph edges;
- does not run semantic or graph retrieval;
- does not alter default `memory_search`.

## Review Decision

The batch diagnostics result closes the post-Slice-2 review evidence gap from
the production opt-in review:

- accepted trial packets can be measured without changing default retrieval;
- held trial packets have explicit status/reason evidence;
- blocked trial packets prove the store-search boundary;
- aggregate evidence is available without leaking sensitive rows.

However, the current implementation still searches before hold inside the gated
trial that produced the packet. That shape is acceptable for audit evidence,
but a production visible hold path should support pre-policy gating when
accurate baseline counts are not explicitly requested. Keep `enforce_hold`
behind another design/review step.

## Verification

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 21 passed.
- `cargo check -p ab-bridge --lib`
  - Passed with existing warnings only.
- `bash -lc 'ulimit -v 2500000; timeout 90 rustfmt --edition 2021 --check crates/bridge/src/mcp_tools.rs crates/bridge/src/trigger_recall_opt_in.rs'`
  - Safely failed under the memory cap because current `mcp_tools.rs` still has
    a large rustfmt diff; `rustfmt_diff::make_diff` attempted a 22GB allocation.
    This is the known formatter failure mode recorded as
    `lesson_rustfmt_check_large_diff_oom_20260623`, not a functional regression
    in the batch diagnostics slice.
- `cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit`
  - Active rows 457, trigger rows 29, projected rows 28.
  - Baseline FTS and baseline shadow: R@10 0.857, MRR 0.786.
  - True hits lost by shadow gate 0; positive cases held 0.
  - Baseline false hits before shadow gate 21; after shadow gate 0.
- `git diff --check`
  - Passed.

## Next Gate

Closed by
`docs/reports/goal-c-u/2026-06-23-trigger-recall-enforce-hold-production-proposal.md`.

Next safe step: write a separate approval-packet schema/review document for
either `audit_only` or `pre_policy_hold` simulation. Do not implement
`enforce_hold`, and do not modify default `memory_search`, until that approval
packet exists and names an exact implementation commit.
