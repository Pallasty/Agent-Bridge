# Trigger-Aware Recall Aio2 Native Mini Corpus

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: continue the read-only trigger-aware recall line after adding an aio2
native trigger-row inventory.

Verdict: `runnable_but_not_authorizing`. Aio2 now has an explicit local mini
corpus and preflight gate, but the first eval does not justify production
retrieval changes. It shows one projected-path miss and broad adjacent-control
false hits, so the next slice should diagnose projection/query behavior and
negative-control semantics before any runtime influence.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

The default Mac-authored corpus remains unchanged. The new aio2-native path is
explicit and opt-in.

The aio2-native corpus contains 12 active trigger rows:

- 6 LSWR verified-outcome ingestion rows;
- 2 Goal C / Controlled RSI rows;
- 4 GHP-1/GHP-1b graph-hygiene rows.

It intentionally excludes the newly created trigger-recall self-observation
rows so the first local corpus is not dominated by the eval line studying
itself.

## Preflight

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Result:

| Metric | Value |
|---|---:|
| DB | `/home/pallasting/.local/share/agent-bridge/state.db` |
| active rows | 442 |
| trigger rows | 14 |
| projected rows | 13 |
| corpus cases | 12 |
| expected key refs | 12 |
| present expected refs | 12 |
| missing expected refs | 0 |
| expected without trigger | 0 |
| ready | true |

## Eval Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Per-mode recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `intent_content` | 0.750 | 1.000 | 1.000 | 0.875 |
| `intent_projected` | 0.750 | 0.917 | 0.917 | 0.833 |
| `cjk_shingle_proj` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected+cjk_acc` | 0.750 | 0.917 | 0.917 | 0.833 |
| `exact_projected` | 0.917 | 1.000 | 1.000 | 0.958 |

Projection delta:

- added top-10 hits over content-only: 0;
- improved first-hit rank: 1 case (`aio2_lswr_g31_apply_lineage`);
- projected miss: 1 case (`aio2_lswr_g25_store_write`);
- CJK fallback did not recover the projected miss.

Negative controls:

- projected false hits against corpus gold keys: 12;
- CJK false hits against corpus gold keys: 12;
- projected+CJK accepted false hits: 12;
- parser errors: 0.

The highest-signal failure is the `aio2_lswr_g25_store_write` row: content-only
finds it at rank 1, exact trigger replay finds it at rank 1, but the held-out
intent query over projected text misses top-10. This suggests the next question
is not CJK tokenization; it is how projected text and query sanitization interact
for mixed gate-number / hyphenated LSWR language.

The adjacent controls are intentionally sharp, and they expose a real weakness:
plain projected FTS cannot distinguish "write graph edges now" or creative
LSWR-vocabulary requests from legitimate state-continuation queries by itself.
That argues for better intent controls and possibly a second-stage semantic or
policy-aware acceptance test in evaluation only.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo check -p ab-bridge --examples
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 9 passed |
| aio2-native preflight | pass, `ready=true` |
| aio2-native eval | pass, metrics above |
| examples check | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this line read-only. The aio2-native corpus is now good enough to detect
local regressions and compare candidate strategies, but it is not positive
evidence for production trigger ranking.

Do not authorize:

- production `memory_search` changes;
- tokenizer/schema migrations;
- memory reindexing;
- runtime ranking or search-order changes;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- memory sync/import;
- memory writes;
- GHP-1b dry_run=false materialization.

## Next Slice

Diagnose `aio2_lswr_g25_store_write` with a debug mode that compares sanitized
precise/OR query terms against both `content` and `fts_content`, then split
negative controls into two buckets:

1. unrelated controls that should return no corpus gold keys;
2. policy/intent adversarial controls that may retrieve relevant memories but
   should be rejected by a later acceptance policy.

Only after that split should this line compare a semantic or policy-aware
acceptance layer against projected FTS.
