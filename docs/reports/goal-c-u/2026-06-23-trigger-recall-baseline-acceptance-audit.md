# Trigger Recall Baseline Acceptance Audit - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Worktree: `/Data/CascadeProjects/agent-bridge`

Base: `53ad6e1` (`test(memory): harden recall eval snapshot open`)

Scope: eval-only baseline shadow acceptance audit; no production retrieval change

## Purpose

This slice implements the design recorded in
`docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-design.md`.

The previous runtime-shaped audit gated only supplemental projected candidates.
That proved supplemental expansion can recover misses without adding false hits,
but it intentionally preserved baseline FTS and therefore retained baseline
false hits. This audit asks the separate next question:

```text
Can baseline FTS candidates be shadow-held by query intent without losing
legitimate continuation recall?
```

## Changes

Code:

- `crates/bridge/examples/trigger_recall_eval.rs`

Added:

- `--aio2-baseline-acceptance-audit`;
- `BaselineAcceptanceAudit`;
- redacted query hash output;
- query-intent allow/hold decision using the existing continuation acceptance
  reason labels;
- before/after baseline FTS candidate counts;
- false-hit removal summary and reason summary;
- regression anchor
  `aio2_trigger_recall_baseline_acceptance_shadow_20260623`;
- tests proving:
  - allowed continuation queries keep baseline candidates visible;
  - rejected controls become shadow holds;
  - rejected shadow holds are not represented as authorized production empty
    results.

This remains scratch-only and read-only: SELECT from the live DB plus in-memory
FTS tables. It does not call `memory_get`, `memory_search`, reindex, write, or
change production ranking.

## Aio2 Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Live store header:

| Metric | Value |
|---|---:|
| active rows | 453 |
| trigger rows | 25 |
| projected rows | 24 |
| corpus cases | 14 |
| negative controls | 8 |
| top_k | 10 |

Recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `baseline_fts` | 0.714 | 0.857 | 0.857 | 0.786 |
| `baseline_shadow` | 0.714 | 0.857 | 0.857 | 0.786 |

Candidate effect:

| Metric | Value |
|---|---:|
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |

Negative controls:

| Metric | Value |
|---|---:|
| baseline false hits before shadow gate | 23 |
| baseline false hits after shadow gate | 0 |
| false hits removed by shadow gate | 23 |

False-hit buckets:

| Bucket | Before | After | Removed |
|---|---:|---:|---:|
| unrelated | 5 | 0 | 5 |
| policy_adversarial | 18 | 0 | 18 |

Held controls by reason:

| Reason | Controls |
|---|---:|
| `creative_non_continuation_intent` | 2 |
| `frontend_dashboard_intent` | 2 |
| `health_dashboard_intent` | 1 |
| `write_bypass_intent` | 2 |

## Interpretation

The shadow baseline gate is clean on the current Aio2 corpus:

- it preserves all current positive baseline hits;
- it holds zero positive cases;
- it removes all 23 current baseline false hits across the negative controls.

This is strong eval evidence for a future opt-in baseline acceptance design, but
it is not production authorization. The audit explicitly reports:

```text
eval_only: true; baseline shadow hold is measurement-only.
Production memory_search, ranking, schema, indexing, graph, semantic retrieval,
MCP surfaces, and memory rows are unchanged.
```

## Verification

Commands:

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Results:

- trigger recall example tests: 27 passed;
- Aio2 baseline acceptance audit: passed and produced the metrics above.

Known unrelated warnings remained visible from existing code:

- mixed-script `beta` test name warning in `ab-store`;
- existing `ab-bridge` unused/private-interface warnings.

## Decision

The baseline acceptance audit gate is landed as an eval-only probe.

The next production-facing step, if approved later, should still be separate:
define an explicit opt-in runtime flag or mode, decide user-visible fallback
semantics for held baseline queries, and preserve this audit as the regression
gate before changing default retrieval behavior.
