# Goal C Trigger-Aware Recall Eval

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-trigger-aware-recall-eval`

Branch: `codex/trigger-aware-recall-eval`

Verdict: `actionable` for adopting a first trigger-aware held-out recall
falsifier. Not actionable for runtime ranking changes.

## Source Anchors

| Anchor | Value |
|---|---|
| base commit | `232cf69847923e6a0f23a1a3e98537c4ed3932bd` |
| base subject | `docs: add mac goal c u refresh report` |
| new harness | `crates/bridge/examples/trigger_recall_eval.rs` |
| live db | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
| corpus | 10 active Mac rows with `continuity_retrieval_trigger` tags |

## Why

Thread #120 post #3833 identified the missing evidence: v36 retrieval-trigger
projection is mechanically populated, but the fixed 18-case `recall_eval` corpus
does not include gold keys from the trigger-tag cohort. That means it cannot
measure whether trigger projection helps the rows it was designed for.

This slice adds a separate read-only example over trigger-tag rows. Each case
has:

- `expect`: the memory key carrying the trigger tag;
- `trigger`: the authored `continuity_retrieval_trigger` text;
- `query`: a separate held-out continuation intent, not the exact trigger text.

The harness reports two modes:

- `intent`: search with the held-out continuation query;
- `exact_trigger`: search with the authored trigger text.

`intent` is the useful continuity metric. `exact_trigger` mainly verifies
whether the projected trigger text is searchable without parser failures.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo run -p ab-bridge --example trigger_recall_eval -- 10
```

Results:

| Check | Result |
|---|---|
| local rustfmt on new file | pass |
| example unit tests | pass, 2 passed |
| live trigger-aware eval | pass, produced report |
| debug case #10 | pass, exposed exact-trigger FTS parser error |

Existing unrelated warnings still appear during Cargo runs:

- `mixed_script_confusables` for the existing `β` test name in `crates/store/src/sqlite.rs`;
- existing `ab-bridge` warnings around private interface and unused Option-E helpers.

Global `cargo fmt --check` was intentionally not used as a gate for this slice:
the current repo has broad pre-existing rustfmt drift unrelated to this file.

## Live Eval Output

```text
# Trigger-aware recall eval - continuity_retrieval_trigger cohort
db:              /Users/pallasting/Library/Application Support/agent-bridge/state.db
corpus:          10 cases (Mac active trigger-tag rows, 2026-06-22)
top_k:           10
mode contract:   exact_trigger = authored tag text; intent = held-out continuation query
read_only:       memory_get + memory_search only; no writes, no reindex, no runtime path change

## Per-mode recall (success@k over 10 cases)
  mode               R@1     R@5    R@10     MRR
  intent           0.700   1.000   1.000   0.833
  exact_trigger    0.900   0.900   0.900   0.900

## Per-case first-hit rank (- = no hit in top 10)
  #   id                            intent exact_trigger  note
  1   s132_handoff                       1             1  BioCortex S132 handoff continuation
  2   s132_evidence                      1             1  BioCortex S132 evidence row
  3   t6_executor_preflight              2             1  AB T6 shadow executor preflight
  4   goal_b_surface_growth              1             1  Goal B tool-surface direction
  5   goal_c_recall_anchor               1             1  Goal C recall anchor
  6   biocortex_gate_program             2             1  BioCortex gate program
  7   ghp12_scope_filter                 1             1  GHP-1.2 exact-scope materialize
  8   goal_c_executor_constraint         3             1  Goal C executor non-authorization
  9   goal_c_u_patch_plan                1             1  Goal C U dry-run patch plan
  10  onsen_handoff                      1           ERR  Cross-project Onsen handoff

## Honest read
  intent misses:        0 case(s)
  exact_trigger misses: 1 case(s) -> #10
  intent errors:        0 case(s)
  exact_trigger errors: 1 case(s) -> #10
```

## Finding

The first trigger-aware held-out cohort is strong on this Mac store:

- `intent` R@10 = `1.000`;
- `intent` R@5 = `1.000`;
- `intent` R@1 = `0.700`;
- `intent` MRR = `0.833`.

That means the current trigger-tag cohort is recoverable from natural
continuation-intent queries in this sample. This does not prove broad production
lift, because the corpus is small and hand-curated, but it gives Goal C a real
falsifier for trigger-projection cohorts.

The run also exposed one hygiene issue:

- case #10 `onsen_handoff` ranks #1 for the held-out intent query;
- the exact authored trigger text errors with
  `backend: memory_search: Error("no such column: hd")`;
- the trigger contains `onsen-hd`, so FTS query sanitization around hyphenated
  trigger text needs a narrow follow-up if exact-trigger replay is meant to be
  robust.

## Non-Authorizations

This report does not authorize:

- runtime search-order changes;
- production ranking changes;
- candidate-set expansion;
- semantic whitening;
- memory reindex;
- graph/PageRank influence;
- memory writes;
- new MCP tools;
- executor or auto-approval behavior.

## Next Step

Adopt `trigger_recall_eval` as a small companion to `recall_eval` for the
trigger-tag cohort, then do one of two narrow follow-ups:

1. Add a regression for hyphenated trigger query sanitization, using `onsen-hd`
   as the concrete failing pattern.
2. Expand the trigger-aware corpus from 10 to at least 30 cases with explicit
   strata: AB continuity, BioCortex, LSWR, Onsen, and negative controls.

The first follow-up is smaller and should come before interpreting
`exact_trigger` as a reliable projection health metric.
