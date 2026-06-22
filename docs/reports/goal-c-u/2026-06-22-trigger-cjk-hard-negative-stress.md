# Trigger-Aware Recall CJK Hard-Negative Stress

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-cjk-hard-negatives`

Branch: `codex/trigger-cjk-hard-negatives`

Base: `fc24171992580f97d67369f46d0685e80d107289`

Verdict: `gate_stress_failed`. Widening the Mac trigger-aware eval with harder
cross-project Chinese negatives shows that the previous `projected+cjk_acc`
gate is not enough. The false-hit source is not only CJK fallback. The
projected-first path itself retrieves gold rows for project-adjacent queries
that explicitly say they do not want those project-state memories.

This remains eval/report only. It does not authorize production retrieval,
tokenizer, ranking, schema, memory, MCP tool, graph, semantic expansion, or
reindex changes.

## What Changed

The Mac `NEGATIVE_CONTROLS` set now includes six harder Chinese controls across
Agent-Bridge, Onsen, and Nexus:

- `hard_ab_tool_profile_cjk`
- `hard_ab_graph_materialize_cjk`
- `hard_onsen_save_cloud_cjk`
- `hard_onsen_visual_decor_cjk`
- `hard_nexus_battle_readability_cjk`
- `hard_nexus_wuxing_art_cjk`

These controls intentionally reuse project vocabulary while stating an
exclusion intent such as `不要召回评测`, `不要GHP部署证据`, `不要Sprint交接`,
or `不要数学模型调研`.

## Results

Command:

```text
cargo run -p ab-bridge --example trigger_recall_eval
```

Key output:

```text
negative_ctrls:  12 controls

## Per-mode recall (success@k over 30 cases)
  mode                   R@1     R@5    R@10     MRR
  intent_content       0.500   0.800   0.900   0.639
  intent_projected     0.700   0.933   0.967   0.796
  cjk_shingle_proj     0.700   0.967   1.000   0.802
  projected+cjk_acc    0.733   0.967   1.000   0.829
  exact_projected      0.933   1.000   1.000   0.967

## Honest read
  intent_projected misses: 1 case(s) -> #27
  cjk_shingle misses:     0 case(s)
  projected+cjk misses:   0 case(s)
  negative controls:       8 false hit(s), 0 parser error(s)
  cjk negative controls:   12 false hit(s), 0 parser error(s)
  projected+cjk controls:  8 false hit(s), 0 parser error(s)
```

New hard-negative false hits include:

```text
hard_ab_tool_profile_cjk:goal_b_surface_growth_gate_engine_finding_20260621@8
hard_ab_graph_materialize_cjk:ab_goal_c_ghp1_live_packet_scope_observation_20260621@4
hard_ab_graph_materialize_cjk:ab_goal_c_ghp12_exact_scope_materialize_gate_deployed_20260621@5
hard_ab_graph_materialize_cjk:ab_goal_c_ghp1_strict_scope_review_packet_deployed_20260621@6
hard_ab_graph_materialize_cjk:goal_b_surface_growth_gate_engine_finding_20260621@8
hard_ab_graph_materialize_cjk:ab_goal_c_ghp12_reconnect_verified_20260621@10
hard_onsen_save_cloud_cjk:session_handoff_onsen_hd_opus_47_20260620@1
hard_nexus_wuxing_art_cjk:nexus_35_tech_wuxing_shengke_v01_20260620@7
```

## Interpretation

The previous six-control gate showed that CJK fallback could repair #27 without
accepted false hits. The harder controls show the next risk:

- `projected+cjk_acc` still fixes #27.
- But it inherits false hits from the projected-first path.
- Therefore a CJK-only acceptance gate is insufficient. The next gate needs an
intent/negation-aware acceptance layer that can reject project-adjacent queries
asking for adjacent but explicitly excluded state.

This is a useful failure. It prevents treating `projected+cjk_acc` as ready for
runtime authority.

## AIO2 Native Boundary

Command:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Current Mac DB result:

```text
corpus cases:             12
expected key refs:        12
present expected refs:    0
missing expected refs:    12
ready:                    false
```

The AIO2 native corpus remains host-local and is not runnable against this Mac
DB. This report therefore uses the Mac 30-case corpus plus the expanded Mac
negative controls as its runnable evidence.

## Verification

```text
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Observed test result:

```text
running 9 tests
test result: ok. 9 passed; 0 failed
```

Known unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name.
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Non-Authorizations

This stress result does not authorize:

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

Add a read-only intent/negation acceptance probe:

1. Keep projected search and CJK candidate generation unchanged.
2. Add an eval-only acceptance predicate that can detect explicit exclusion
   terms such as `不要`, `不是`, `只要`, and `without`.
3. Compare false-hit reduction on the 12-control set while preserving #27
   recovery.
