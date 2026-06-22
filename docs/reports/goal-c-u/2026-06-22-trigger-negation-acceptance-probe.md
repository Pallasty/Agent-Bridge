# Trigger Recall Negation Acceptance Probe

Date: 2026-06-22
Branch: `codex/trigger-negation-acceptance-probe`
Base: `eef9125 test(memory): stress trigger cjk hard negatives`
Rebased verification base: `abbae85 test(memory): diagnose aio2 trigger projection miss`

## Scope

This is an eval-only probe for Goal C trigger-aware recall. It does not change
production retrieval, ranking, schema, MCP tools, or memory writes.

The previous hard-negative stress report showed that `projected+cjk_acc`
preserved recall but still accepted 8 corpus-gold false hits from 12 negative
controls. This probe asks whether an explicit exclusion-intent filter can remove
those hard false hits without losing positive recall.

## Probe

New eval mode:

- `projected+intent`: run `projected+cjk_acc`, then reject candidates whose
  projected text matches explicit exclusion clauses in the query.

Accepted exclusion markers in this first probe:

- Chinese: `不要`
- English: `without`, `not`

Non-marker:

- `不是` is intentionally not treated as a hard exclusion. A first local run
  showed it over-filtered positive non-authorization queries such as "why
  report-first rather than a new MCP tool" because the correct memory can
  contain the rejected alternative for explanation.

## Mac Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval
```

DB:

`/Users/pallasting/Library/Application Support/agent-bridge/state.db`

Corpus:

- Active rows: 3003
- Trigger rows: 135
- Projected rows: 135
- Positive cases: 30
- Negative controls: 12

Recall:

| mode | R@1 | R@5 | R@10 | MRR |
| --- | ---: | ---: | ---: | ---: |
| `intent_content` | 0.500 | 0.800 | 0.900 | 0.639 |
| `intent_projected` | 0.700 | 0.933 | 0.967 | 0.796 |
| `cjk_shingle_proj` | 0.700 | 0.967 | 1.000 | 0.802 |
| `projected+cjk_acc` | 0.733 | 0.967 | 1.000 | 0.829 |
| `projected+intent` | 0.733 | 0.967 | 1.000 | 0.829 |
| `exact_projected` | 0.933 | 1.000 | 1.000 | 0.967 |

Negative controls:

| mode | false hits | parser errors |
| --- | ---: | ---: |
| `intent_projected` | 8 | 0 |
| `cjk_shingle_proj` | 12 | 0 |
| `projected+cjk_acc` | 8 | 0 |
| `projected+intent` | 1 | 0 |

Remaining false hit:

- `hard_nexus_wuxing_art_cjk:nexus_35_tech_wuxing_shengke_v01_20260620@7`

Interpretation:

- The explicit exclusion-intent filter preserved the `projected+cjk_acc` positive
  recall result on the Mac corpus: 0 misses in top 10.
- It reduced accepted hard-control false hits from 8 to 1.
- The remaining false hit is an art-vs-design-review semantic boundary. It is
  not obviously solvable with a literal exclusion-clause filter alone.

## AIO2 Native Boundary

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Result on this Mac host:

- Exit code: 1
- Expected key refs: 12
- Present expected refs: 0
- Missing expected refs: 12
- Ready: false

This is expected: the AIO2-native gold corpus is host-local and is not runnable
against the current Mac DB.

## Verification

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Unit tests:

- 13 passed
- Added coverage for explicit exclusion clause extraction.
- Added coverage for ASCII and CJK exclusion matching.
- Added coverage that the intent filter rejects an excluded candidate while
  retaining an allowed interface-inventory candidate.

Known unrelated warnings:

- Existing `ab-store` mixed-script beta test-name warning.
- Existing `ab-bridge` warnings around private interfaces and unused Option E
  helpers.

## Decision

`projected+intent` is a useful eval-only acceptance probe. It is strong enough
to justify another narrow round over hard controls, but not yet enough to ship
as production retrieval behavior.

Recommended next slice:

1. Add targeted controls for contrastive non-authorization queries that use
   "not"/"rather than" language.
2. Add a small semantic-intent comparator for the remaining Wuxing art-vs-design
   false hit.
3. Keep production retrieval untouched until the acceptance probe has stable
   positive recall and low false positives across both Mac and host-local AIO2
   corpora.
