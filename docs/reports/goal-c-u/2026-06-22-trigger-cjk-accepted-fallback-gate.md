# Trigger-Aware Recall CJK Accepted Fallback Gate

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-cjk-acceptance-gate`

Branch: `codex/trigger-cjk-acceptance-gate`

Base: `77704f2f1e27ef596d2fb3fdac00a81a8097abb2`

Verdict: `eval_gate_promising`. A two-stage read-only eval separates CJK
candidate recall from final acceptance. The existing projected FTS path remains
the primary path; CJK shingles are used only as a fallback when projected search
returns no candidates. The fallback then requires a conservative CJK trigram
overlap gate before accepting candidates.

This does not authorize production retrieval, tokenizer, ranking, schema,
memory, MCP tool, graph, semantic expansion, or reindex changes.

## What Changed

The trigger-aware eval now reports:

- `cjk_shingle_proj`: broad scratch-only CJK shingle candidate generation.
- `projected+cjk_acc`: existing projected search first; if projected search
  misses, use CJK shingle candidates filtered by the acceptance gate.

Acceptance gate:

```text
require >= 4 shared CJK trigram terms between query and candidate projected text
```

The guard is intentionally narrow. It tests whether the #27 recovery can be
accepted without letting project-adjacent CJK distractors through.

## Results

Command:

```text
cargo run -p ab-bridge --example trigger_recall_eval
```

Key output:

```text
## Per-mode recall (success@k over 30 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.500   0.800   0.900   0.639
  intent_projected     0.700   0.933   0.967   0.796
  cjk_shingle_proj     0.700   0.967   1.000   0.802
  projected+cjk_acc    0.733   0.967   1.000   0.829
  exact_projected      0.933   1.000   1.000   0.967

## CJK shingle recovery probe
  negative false hits: 4

## Projected plus CJK accepted-candidate fallback
  added top-10 hits over projected: 1 case(s) -> #27
  improved first-hit rank over projected: 1 case(s) -> #27
  accepted false hits: 0
  parser errors: 0

## Honest read
  intent_projected misses: 1 case(s) -> #27
  cjk_shingle misses:     0 case(s)
  projected+cjk misses:   0 case(s)
  cjk negative controls:   4 false hit(s), 0 parser error(s)
  projected+cjk controls:  0 false hit(s), 0 parser error(s)
```

Debug #27:

```text
## intent_projected

## cjk_shingle_projected
   1. nexus_wuxing_shengke_golden_ratio_survey_20260621 <== EXPECTED
   2. nexus_35_tech_wuxing_shengke_v01_20260620
   ...

## projected_plus_cjk_accepted
   1. nexus_wuxing_shengke_golden_ratio_survey_20260621 <== EXPECTED
   2. nexus_35_tech_wuxing_shengke_v01_20260620
```

## Interpretation

The result separates three claims:

- Current projected FTS is still the stable baseline: it has 0 false hits on the
  six negative controls, but misses #27.
- Raw CJK shingle candidate generation fixes #27, but project-adjacent CJK
  distractors create false hits.
- Projected-first plus accepted CJK fallback keeps the #27 lift and reduces
  accepted false hits to 0 on this corpus/control set.

This is promising as an eval gate, not a runtime design decision. The 30-case
corpus and six controls are still too small to authorize production behavior.

## Verification

```text
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- 27
cargo run -p ab-bridge --example trigger_recall_eval
```

Observed test result:

```text
running 7 tests
test result: ok. 7 passed; 0 failed
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

Keep this as a read-only gate and widen evidence before discussing runtime
authority:

1. Add more CJK project-adjacent negatives from Agent-Bridge, Onsen, and Nexus
   lanes.
2. Compare the trigram-overlap fallback against a semantic rerank fallback on
   the same fixed candidate set.
3. Track separate metrics: `candidate_recall@k`, `accepted_recall@k`, and
   `accepted_false_hits`.
