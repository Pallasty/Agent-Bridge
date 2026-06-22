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
| harness | `crates/bridge/examples/trigger_recall_eval.rs` |
| live DB | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
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

The harness compares three modes:

- `intent_content`: held-out query over authored `memories.content`;
- `intent_projected`: the same held-out query over `COALESCE(fts_content, content)`;
- `exact_projected`: authored trigger text over `COALESCE(fts_content, content)`.

`intent_content` vs `intent_projected` isolates the projection itself. It does
not use `memory_get`, `memory_search`, access count, importance, recency, graph
expansion, or semantic embeddings.

## Verification

Commands:

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
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
| debug case #10 | pass, confirmed exact-trigger FTS parser error |

Existing unrelated warnings still appear during Cargo runs:

- `mixed_script_confusables` for the existing `beta` test name in
  `crates/store/src/sqlite.rs`;
- existing `ab-bridge` warnings around private interface and unused Option-E
  helpers.

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

The first trigger-aware held-out cohort shows a real, narrow projection gain:

- `intent_projected` improves R@10 from `0.900` to `1.000`;
- `intent_projected` improves R@5 from `0.800` to `1.000`;
- `intent_projected` improves R@1 from `0.600` to `0.700`;
- `intent_projected` improves MRR from `0.714` to `0.817`;
- projection adds one top-10 hit over content-only, case #8
  `goal_c_executor_constraint`;
- projection improves first-hit rank for cases #2, #6, and #8.

This supports the v36 trigger projection as a candidate-visibility improvement
for its own cohort. It does not authorize production ranking changes: the corpus
is small, hand-curated, and measures only temporary FTS candidate visibility.

The run also exposed one parser hygiene issue:

- case #10 `onsen_handoff` ranks #1 for the held-out intent query in both
  content and projected indexes;
- the exact authored trigger text errors with `no such column: hd`;
- the trigger contains `onsen-hd` plus operator-like punctuation, so exact
  trigger replay needs a narrow FTS sanitizer follow-up before it can be used as
  a robust projection-health metric.

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

Adopt `trigger_recall_eval` as a companion to `recall_eval` for the trigger-tag
cohort, then do two narrow follow-ups:

1. Add a regression for exact-trigger FTS parser hygiene using `onsen-hd` /
   punctuation as the concrete failing pattern.
2. Expand the trigger-aware corpus from 10 to at least 30 cases with explicit
   strata: AB continuity, BioCortex, LSWR, Onsen, and negative controls.

The parser regression should come first because it makes `exact_projected`
usable as a low-level projection-health check.
