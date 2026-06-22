# Trigger-Aware Recall CJK Expanded Negative Controls

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-cjk-negative-controls`

Branch: `codex/trigger-cjk-negative-controls`

Base: `9a0e3d5a7ad46c200743d7f9626067715764b426`

Verdict: `gate_tightened`. The landed scratch-only
`cjk_shingle_projected` probe still recovers the #27 CJK miss, but expanded
project-adjacent CJK negative controls expose false-hit risk. This strengthens
the evidence that CJK shingles should be treated as candidate generation only,
not as a production acceptance/ranking path by themselves.

## What Changed

The trigger-aware eval now keeps the original unrelated controls and adds three
project-adjacent CJK controls:

- `project_adjacent_cjk_tourism`: shares `五行`, `黄金比例`, and `平衡`, but
  asks about tourism, photography, and shopping.
- `project_adjacent_cjk_health`: shares Wuxing/balance/golden-ratio vocabulary,
  but asks about diet and fitness.
- `project_adjacent_nexus_visual`: shares Nexus and Wuxing vocabulary, but asks
  about visual skins and balance feedback rather than the math survey.

These controls are intentionally closer to the CJK #27 failure mode than the
previous unrelated weather/recipe/puzzle controls.

## Results

Command:

```text
cargo run -p ab-bridge --example trigger_recall_eval
```

Key output:

```text
negative_ctrls:  6 controls

## Per-mode recall (success@k over 30 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.500   0.800   0.900   0.639
  intent_projected     0.700   0.933   0.967   0.796
  cjk_shingle_proj     0.700   0.967   1.000   0.802
  exact_projected      0.933   1.000   1.000   0.967

## CJK shingle recovery probe
  added top-10 hits over projected: 1 case(s) -> #27
  improved first-hit rank over projected: 3 case(s) -> #3, #6, #27
  negative false hits: 4
  parser errors: 0

## Honest read
  intent_projected misses: 1 case(s) -> #27
  cjk_shingle misses:     0 case(s)
  negative controls:       0 false hit(s), 0 parser error(s)
  cjk negative controls:   4 false hit(s), 0 parser error(s)
```

False hits:

```text
project_adjacent_cjk_tourism:nexus_wuxing_shengke_golden_ratio_survey_20260621@1
project_adjacent_cjk_tourism:nexus_35_tech_wuxing_shengke_v01_20260620@3
project_adjacent_cjk_health:nexus_wuxing_shengke_golden_ratio_survey_20260621@1
project_adjacent_cjk_health:nexus_35_tech_wuxing_shengke_v01_20260620@3
```

## Interpretation

The result is useful because it separates two claims:

- Candidate visibility claim: still true. CJK shingles recover the one remaining
  #27 projected miss and move `cjk_shingle_proj` to `R@10 = 1.000`.
- Acceptance claim: not proven. Project-adjacent distractors can rank Nexus
  Wuxing gold rows highly under the shingle probe.

The normal `intent_projected` path remains clean on all six controls, so the
false-hit growth is specific to the scratch CJK shingle candidate path.

## Verification

```text
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
```

Observed test result:

```text
running 5 tests
test result: ok. 5 passed; 0 failed
```

Known unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name.
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Non-Authorizations

This follow-up does not authorize:

- production `memory_search` changes;
- tokenizer/schema migrations;
- memory reindexing;
- runtime ranking or search-order changes;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- new MCP tools;
- memory writes.

## Recommended Next Slice

Promote the eval shape from one-stage recall to a two-stage gate:

1. `candidate_recall@k`: allow CJK shingle or other expansion methods to prove
   that the expected row is visible.
2. `accepted_false_hits`: require a separate acceptance/rerank filter to reject
   project-adjacent distractors before any runtime retrieval authority is
   considered.

Possible acceptance filters to compare in read-only eval only:

- trigger-field weighting over raw content matches;
- kind/scope/continuity metadata constraints;
- query-intent lexical overlap against authored trigger text;
- semantic rerank over the generated candidate set.
