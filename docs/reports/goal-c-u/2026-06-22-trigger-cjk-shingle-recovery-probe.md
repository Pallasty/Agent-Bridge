# Trigger-Aware Recall CJK Shingle Recovery Probe

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge`

Branch: `master`

Verdict: `promising_eval_probe`. A scratch-only CJK trigram index recovers the
single projected miss in the 30-case trigger-aware corpus without false hits in
the current negative controls. This does not authorize runtime retrieval,
tokenizer, schema, ranking, or reindex changes.

## Source Anchors

| Anchor | Value |
|---|---|
| base commit | `af511c3ada89a68e6db80e7635825681a4fec79d` |
| harness | `crates/bridge/examples/trigger_recall_eval.rs` |
| diagnostic report | `docs/reports/goal-c-u/2026-06-22-trigger-cjk-tokenization-diagnostic.md` |
| live DB | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
| corpus | 30 active Mac rows with `continuity_retrieval_trigger` tags |
| negative controls | 3 unrelated queries checked against corpus gold keys |

## Probe

The harness now adds an eval-only mode:

- `cjk_shingle_projected`: search the held-out query against a scratch
  in-memory FTS table built from projected text plus generated CJK character
  trigrams.

Implementation constraints:

- uses the same read-only live DB load as the existing harness;
- writes only to an in-memory scratch table;
- generates `cjk_<trigram>` pseudo tokens for CJK Unified Ideograph runs;
- leaves production `memory_search`, schema, tokenizer, indexing, and ranking
  untouched;
- does not call `memory_get`, `memory_search`, semantic embeddings, graph
  expansion, access count, recency, or importance.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo run -p ab-bridge --example trigger_recall_eval -- 27
```

Results:

| Check | Result |
|---|---|
| local rustfmt on example | pass |
| example unit tests | pass, 5 passed |
| live trigger-aware eval | pass, 30-case report |
| debug case #27 | pass, `cjk_shingle_projected` ranks expected key at #1 |

Existing unrelated warnings still appear during Cargo runs:

- `mixed_script_confusables` for the existing beta test name in
  `crates/store/src/sqlite.rs`;
- existing `ab-bridge` warnings around private interface and unused Option-E
  helpers.

## Live Eval Output

```text
# Trigger-aware recall eval - continuity_retrieval_trigger cohort
db:              /Users/pallasting/Library/Application Support/agent-bridge/state.db
active rows:     3000
trigger rows:    135
projected rows:  135
corpus:          30 cases (Mac active trigger-tag rows, 2026-06-22)
negative_ctrls:  3 controls
top_k:           10

## Per-mode recall (success@k over 30 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.500   0.800   0.900   0.639
  intent_projected     0.700   0.933   0.967   0.796
  cjk_shingle_proj     0.700   0.967   1.000   0.802
  exact_projected      0.933   1.000   1.000   0.967

## CJK shingle recovery probe
  added top-10 hits over projected: 1 case(s) -> #27
  improved first-hit rank over projected: 3 case(s) -> #3, #6, #27
  negative false hits: 0
  parser errors: 0

## Honest read
  intent_content misses:   3 case(s) -> #8, #23, #27
  intent_projected misses: 1 case(s) -> #27
  cjk_shingle misses:     0 case(s)
  exact_projected errors:  0 case(s)
  negative controls:       0 false hit(s), 0 parser error(s)
  cjk negative controls:   0 false hit(s), 0 parser error(s)
```

Debug case #27:

```text
## cjk_shingle_projected
   1. nexus_wuxing_shengke_golden_ratio_survey_20260621 <== EXPECTED
   2. work_memory_5aca43411e25_shared_active
   3. nexus_35_tech_wuxing_shengke_v01_20260620
   4. nexus_tfe_research_arc_capstone_20260606
   5. curated_implicit_todoe5f01281
   6. curated_implicit_todoba92845f
   7. nexus_wuxing_phi2_not_glv_calibration_target_20260622
   8. nexus_session_20260604_handoff
   9. nexus_wuxing_tfe_redteam_static_not_dynamical_20260605
  10. nexus_wuxing_grand_unification_20260603
```

## Finding

The scratch CJK shingle probe directly addresses the #27 failure mode:

- baseline `intent_projected` has no candidate for #27;
- `cjk_shingle_projected` ranks the expected key at #1;
- the 30-case R@10 moves from `0.967` to `1.000`;
- current negative controls remain clean.

The probe also changes ranks for already-successful cases:

- improves #3 and #6;
- lowers a few already-successful ranks, for example #1, #8, #16, #18, #20,
  and #23.

That rank movement is acceptable for an eval probe but important evidence
against directly replacing the production FTS candidate path without a stronger
gate.

## Non-Authorizations

This report does not authorize:

- production `memory_search` changes;
- tokenizer/schema migrations;
- memory reindexing;
- runtime ranking or search-order changes;
- candidate-set widening;
- semantic expansion;
- graph/PageRank influence;
- new MCP tools;
- memory writes.

## Next Step

Promote this only to a larger read-only gate:

1. expand negative controls with Chinese project-adjacent distractors, not just
   unrelated daily-life phrases;
2. compare CJK trigram shingling against semantic candidate expansion on the
   same fixed corpus;
3. require recall lift without false-hit growth before discussing runtime
   retrieval authority.
