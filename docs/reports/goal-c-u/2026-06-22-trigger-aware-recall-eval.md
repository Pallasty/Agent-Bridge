# Goal C Trigger-Aware Recall Eval

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-trigger-aware-corpus-v2`

Branch: `codex/trigger-aware-corpus-v2`

Verdict: `actionable` for keeping `trigger_recall_eval` as a read-only
continuity falsifier. Not actionable for runtime ranking changes.

## Source Anchors

| Anchor | Value |
|---|---|
| base commit | `4285f2e23fbc550a1a5f75f6d5139e91139f45e2` |
| base subject | `fix(memory): sanitize trigger recall punctuation` |
| harness | `crates/bridge/examples/trigger_recall_eval.rs` |
| live DB | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
| corpus | 30 active Mac rows with `continuity_retrieval_trigger` tags |
| negative controls | 3 unrelated queries checked against corpus gold keys |

## Why

Thread #120 identified the missing evidence: v36 retrieval-trigger projection is
mechanically populated, but the fixed `recall_eval` corpus does not measure the
trigger-tag cohort directly. This harness opens the live store read-only, copies
active rows into in-memory FTS tables, and compares:

- `intent_content`: held-out query over authored `memories.content`;
- `intent_projected`: same held-out query over `COALESCE(fts_content, content)`;
- `exact_projected`: authored trigger text over `COALESCE(fts_content, content)`.

The eval does not use `memory_get`, `memory_search`, access count, importance,
recency, graph expansion, semantic embeddings, writes, or reindexing.

The 30-case corpus now spans AB T6/memory-continuity, BioCortex, Goal B, Goal C,
graph hygiene, Nexus, Onsen, and Palace. The negative controls fail the run if
unrelated queries retrieve any corpus gold key in the projected index.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo run -p ab-bridge --example trigger_recall_eval -- 10
cargo run -p ab-bridge --example trigger_recall_eval -- 27
```

Results:

| Check | Result |
|---|---|
| local rustfmt on example | pass |
| example unit tests | pass, 3 passed |
| live trigger-aware eval | pass, 30-case report |
| debug case #10 | pass, exact-trigger sanitizer recovery remains fixed |
| debug case #27 | pass, exposes a Chinese paraphrase/tokenization miss |

Existing unrelated warnings still appear during Cargo runs:

- `mixed_script_confusables` for the existing beta test name in
  `crates/store/src/sqlite.rs`;
- existing `ab-bridge` warnings around private interface and unused Option-E
  helpers.

Global `cargo fmt --check` was intentionally not used as a gate for this slice:
the current repo has broad pre-existing rustfmt drift unrelated to this example.

## Live Eval Output

```text
# Trigger-aware recall eval - continuity_retrieval_trigger cohort
db:              /Users/pallasting/Library/Application Support/agent-bridge/state.db
active rows:     2995
trigger rows:    134
projected rows:  134
corpus:          30 cases (Mac active trigger-tag rows, 2026-06-22)
negative_ctrls:  3 controls
top_k:           10
mode contract:   intent_content vs intent_projected isolates trigger projection
read_only:       SELECT + in-memory FTS only; no memory_get, memory_search, writes, or reindex

## Per-mode recall (success@k over 30 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.500   0.800   0.900   0.639
  intent_projected     0.700   0.933   0.967   0.796
  exact_projected      0.933   1.000   1.000   0.967

## Corpus strata
  ab_t6            7
  biocortex        7
  goal_b           1
  goal_c           6
  graph_hygiene    4
  nexus            2
  onsen            1
  palace           2

## Projection delta
  added top-10 hits over content-only: 2 case(s) -> #8, #23
  improved first-hit rank:              9 case(s) -> #2, #6, #8, #11, #12, #13, #17, #21, #23

## Negative controls
  projected false hits against corpus gold keys: 0
  projected parser errors: 0

## Honest read
  intent_content misses:   3 case(s) -> #8, #23, #27
  intent_projected misses: 1 case(s) -> #27
  exact_projected errors:  0 case(s)
  negative controls:       0 false hit(s), 0 parser error(s)
```

## Finding

The broader trigger-aware held-out cohort still shows a real, narrow projection
gain:

- `intent_projected` improves R@10 from `0.900` to `0.967`;
- `intent_projected` improves R@5 from `0.800` to `0.933`;
- `intent_projected` improves R@1 from `0.500` to `0.700`;
- `intent_projected` improves MRR from `0.639` to `0.796`;
- projection adds two top-10 hits over content-only: #8
  `goal_c_executor_constraint` and #23 `goal_c_u_surface`;
- projection improves first-hit rank for nine cases:
  #2, #6, #8, #11, #12, #13, #17, #21, and #23.

The exact-trigger parser health check is now clean across all 30 cases:
`exact_projected errors: 0`.

The useful new miss is #27 `nexus_wuxing_math`:

- `exact_projected` ranks the expected key at #1, so the trigger is projected
  and replayable;
- the held-out Chinese intent query returns no FTS candidates in either content
  or projected mode;
- this points to a Chinese paraphrase/tokenization blind spot rather than a
  trigger-projection bug.

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
cohort. The next evaluation-only slice should investigate the #27 Chinese
paraphrase/tokenization miss and add more LSWR-specific cases once fresh
trigger-tag rows exist. Runtime retrieval authority remains out of scope.
