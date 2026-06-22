# Trigger Recall Wuxing Boundary Diagnostic

Date: 2026-06-22
Branch: `codex/trigger-wuxing-boundary-diagnostic`
Base: `15d536a test(memory): probe trigger negation acceptance`
Intermediate verification base: `f4259f4 test(memory): compare aio2 trigger candidate assembly`
Final verification base: `c595917 test(memory): add trigger contrastive controls`

## Scope

This is an eval-only diagnostic slice for remaining `projected+intent` false
hits from the negation acceptance probe.

It does not change production retrieval, ranking, schema, tokenizer, MCP tools,
memory writes, or memory indexing.

Board context:

- #3888 claimed and later landed the contrastive non-authorization control lane
  as `c595917`.
- This slice is deliberately non-overlapping: add a reusable false-hit boundary
  diagnostic surface without adding new contrastive controls.

## Target

Original target false hit, observed before `c595917`:

```text
hard_nexus_wuxing_art_cjk:nexus_35_tech_wuxing_shengke_v01_20260620@7
```

Negative-control query:

```text
Nexus 五行 UI 图标 配色 角色皮肤 美术规格 只要视觉草案 不要数学模型调研
```

The explicit exclusion clause extracted from this query is:

```text
数学模型调研
```

## Code Change

`crates/bridge/examples/trigger_recall_eval.rs` now keeps
`projected+intent` false hits as structured records and prints an
`Explicit exclusion boundary diagnostics` section for remaining false hits.

For each remaining false hit it reports:

- original negative-control note and query;
- extracted explicit exclusion clauses;
- whether the candidate matched the exclusion clause;
- CJK trigram overlap against the full query;
- ASCII overlap against the full query;
- per-clause CJK/ASCII overlap;
- projected text preview.

## Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval
```

Mac eval summary after rebasing onto `c595917`:

| mode | R@1 | R@5 | R@10 | MRR |
| --- | ---: | ---: | ---: | ---: |
| `projected+cjk_acc` | 0.733 | 0.967 | 1.000 | 0.829 |
| `projected+intent` | 0.733 | 0.967 | 1.000 | 0.829 |

Negative controls after the contrastive lane expanded the set to 16 controls:

| mode | false hits | parser errors |
| --- | ---: | ---: |
| `projected+cjk_acc` | 19 | 0 |
| `projected+intent` | 0 | 0 |

The new diagnostics section now reports:

```text
no projected+intent false hits to diagnose
```

## Intermediate Diagnostic

Before `c595917`, the same diagnostic surface showed this for the remaining
Wuxing false hit:

```text
hit: hard_nexus_wuxing_art_cjk:nexus_35_tech_wuxing_shengke_v01_20260620@7
clauses: 数学模型调研
exclusion_match: false
query_cjk_overlap: 0
query_ascii_overlap: nexus
clause_diag: cjk_overlap=0 ascii_overlap=- clause=数学模型调研
```

Intermediate interpretation:

- The Wuxing false hit was not a failure of the explicit exclusion-clause
  filter: the excluded phrase `数学模型调研` does not match the candidate.
- It was also not a CJK trigram acceptance issue: full-query CJK trigram overlap
  is 0 for this hit.
- The observed surface overlap was broad project identity (`nexus`) plus the
  broader FTS candidate set. This points to a semantic boundary/rerank problem:
  Wuxing art/UI/spec intent vs #35 design-review memory.
- The rebase-added candidate assembly probes did not change the read: both
  `projected_union` and `projected_oracle` still miss case #27 and do not
  affect the false-hit diagnosis.

Final interpretation after `c595917`:

- The contrastive-control lane removed the Wuxing false hit and all other
  `projected+intent` negative-control false hits in the current 16-control Mac
  eval.
- The diagnostic output remains useful as a regression surface: if future
  controls reintroduce `projected+intent` false hits, the eval now prints why a
  candidate survived the explicit exclusion filter.

## Verification

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
```

Unit tests:

- 15 passed.
- Added `wuxing_art_remaining_false_hit_is_query_overlap_not_exclusion_clause_overlap`.

Known unrelated warnings:

- Existing `ab-store` mixed-script beta test-name warning.
- Existing `ab-bridge` warnings around private interfaces and unused Option E
  helpers.

## Decision

Do not widen the literal exclusion filter based on the old Wuxing hit. The
current contrastive-control path already clears it without production retrieval
changes.

Recommended next non-overlapping follow-up:

1. Keep the diagnostic surface in the eval output.
2. Add a small semantic-intent comparator/rerank probe with explicit
   intent buckets such as `art_ui_spec`, `design_review`, `math_model`,
   `handoff`, and `deployment_evidence`.
3. Keep `projected+intent` eval-only until the semantic-boundary controls
   stabilize across Mac and host-local AIO2 corpora.
