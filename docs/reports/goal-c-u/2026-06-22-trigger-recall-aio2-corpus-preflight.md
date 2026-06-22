# Trigger-Aware Recall Aio2 Corpus Preflight

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: continue the read-only trigger-aware recall line after expanded CJK
negative controls.

Verdict: `blocked_by_corpus_source_mismatch` on aio2 live DB. The harness now
has an explicit corpus preflight, so this is a data/source-host blocker rather
than a retrieval failure.

## Context

`bb587b6 test(memory): expand trigger cjk negative controls` landed the
project-adjacent CJK controls. `367c13e test(memory): gate trigger cjk accepted
fallback` then added a two-stage eval gate over the same Mac-authored corpus.
The current evidence is:

- `cjk_shingle_projected` still recovers the #27 CJK miss and reaches
  `R@10 = 1.000` on the Mac-authored 30-case corpus.
- Expanded project-adjacent CJK controls add 4 false hits:
  Wuxing/golden-ratio tourism and health distractors match the Nexus Wuxing
  gold rows.
- `projected+cjk_acc`, the projected-first accepted fallback, keeps the #27
  lift and reports 0 accepted false hits on the current six-control set.
- Therefore CJK shingles remain useful as a candidate-visibility probe, and the
  accepted fallback is promising as an eval gate, but neither path authorizes
  production retrieval behavior.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
```

The mode:

- opens the selected DB read-only;
- reports active, trigger, projected, and expected-key coverage;
- lists missing gold keys and expected rows without trigger tags;
- exits non-zero when the corpus is not runnable against that DB;
- performs no `memory_search`, no writes, no reindexing, and no runtime ranking
  changes.

This prevents cross-node corpus drift from being misread as a recall failure.

## Aio2 Live Preflight

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
```

Result:

| Metric | Value |
|---|---:|
| DB | `/home/pallasting/.local/share/agent-bridge/state.db` |
| active rows | 440 |
| trigger rows | 12 |
| projected rows | 11 |
| corpus cases | 30 |
| expected key refs | 30 |
| present expected refs | 0 |
| missing expected refs | 30 |
| expected without trigger | 0 |
| ready | false |

The normal live eval and debug run both stop at the same preflight problem:

```text
s132_handoff expected key missing:
biocortex_rs_s132_static_experiment_design_review_preflight_handoff_20260622
```

The expanded corpus was built from active Mac trigger-tag rows, while this aio2
DB does not contain those 30 gold keys. A filesystem search on aio2 found the
keys only in source reports and the example harness, not in local memory rows or
state exports.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 9 passed |
| corpus preflight | expected non-zero on aio2, `ready=false` |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Do not use aio2 live DB to judge the Mac-authored trigger recall corpus until
one of these is true:

1. the matching Mac DB/snapshot is provided via `AB_BASELINE_DB`;
2. cross-device memory sync/import is explicitly authorized and verified to
   include the 30 gold keys;
3. a separate aio2-native trigger corpus is curated from aio2 active rows.

The current read-only finding is still valuable: it tightens the harness so
future runs can fail early and honestly on corpus coverage.

## Non-Authorizations

This report does not authorize:

- production `memory_search` changes;
- tokenizer/schema migrations;
- memory reindexing;
- runtime ranking or search-order changes;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- memory sync/import;
- memory writes;
- new MCP tools.

## Next Slice

Keep the two-stage fallback as a read-only eval gate and widen evidence before
any runtime retrieval authority:

1. add more CJK project-adjacent negatives from Agent-Bridge, Onsen, and Nexus
   lanes;
2. compare the trigram-overlap accepted fallback against a semantic rerank
   fallback on the same fixed candidate set;
3. track separate `candidate_recall@k`, `accepted_recall@k`, and
   `accepted_false_hits` metrics.

For aio2 specifically, choose between importing the matching Mac baseline for a
reproduction run or curating a small aio2-native trigger corpus first.
