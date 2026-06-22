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

This slice adds a separate read-only example over trigger-tag rows. It opens the
live store read-only, copies active rows into two temporary in-memory FTS tables,
and compares authored `content` against projected `fts_content`. Each case has:

- `expect`: the memory key carrying the trigger tag;
- `trigger`: the authored `continuity_retrieval_trigger` text;
- `query`: a separate held-out continuation intent, not the exact trigger text.

The harness reports three modes:

- `intent_content`: held-out query over authored `memories.content`;
- `intent_projected`: the same held-out query over `memories.fts_content`;
- `exact_projected`: authored trigger text over `memories.fts_content`.

`intent_projected` is the useful continuity metric. The delta between
`intent_content` and `intent_projected` isolates the retrieval-trigger
projection effect without production ranking, recency, access-count, graph, or
semantic embedding factors. `exact_projected` mainly verifies whether the
authored trigger text itself is replayable through the FTS parser.

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
| example unit tests | pass, 3 passed |
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
active rows:     2995
trigger rows:    134
projected rows:  134
corpus:          10 cases (Mac active trigger-tag rows, 2026-06-22)
top_k:           10
mode contract:   intent_content vs intent_projected isolates trigger projection
read_only:       SELECT + in-memory FTS only; no memory_get, memory_search, writes, or reindex

## Per-mode recall (success@k over 10 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.600   0.800   0.900   0.714
  intent_projected     0.700   1.000   1.000   0.817
  exact_projected      0.900   0.900   0.900   0.900

## Projection delta
  added top-10 hits over content-only: 1 case(s) -> #8
  improved first-hit rank:              3 case(s) -> #2, #6, #8

## Per-case first-hit rank (- = no hit in top 10; ERR = FTS parser error)
  #   id                            content  projected      exact  note
  1   s132_handoff                        1          1          1  BioCortex S132 handoff continuation
  2   s132_evidence                       2          1          1  BioCortex S132 evidence row
  3   t6_executor_preflight               2          2          1  AB T6 shadow executor preflight
  4   goal_b_surface_growth               1          1          1  Goal B tool-surface direction
  5   goal_c_recall_anchor                1          1          1  Goal C recall anchor
  6   biocortex_gate_program              7          3          1  BioCortex gate program
  7   ghp12_scope_filter                  1          1          1  GHP-1.2 exact-scope materialize
  8   goal_c_executor_constraint          -          3          1  Goal C executor non-authorization
  9   goal_c_u_patch_plan                 1          1          1  Goal C U dry-run patch plan
  10  onsen_handoff                       1          1        ERR  Cross-project Onsen handoff

## Honest read
  intent_content misses:   1 case(s) -> #8
  intent_projected misses: 0 case(s)
  exact_projected errors:  1 case(s) -> #10
```

## Finding

The first trigger-aware held-out cohort is strong on this Mac store and shows a
measurable projection effect:

- `intent_content` R@10 = `0.900`, MRR = `0.714`;
- `intent_projected` R@10 = `1.000`, MRR = `0.817`;
- projection added 1 top-10 hit over content-only, case #8
  `goal_c_executor_constraint`;
- projection improved first-hit rank for 3 cases: #2, #6, and #8.

That means the current trigger-tag cohort is recoverable from natural
continuation-intent queries in this sample, and the projection makes at least one
otherwise-missed case visible. This does not prove broad production lift,
because the corpus is small and hand-curated, but it gives Goal C a real
falsifier for trigger-projection cohorts.

The run also exposed one hygiene issue:

- case #10 `onsen_handoff` ranks #1 for both `intent_content` and
  `intent_projected`;
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
