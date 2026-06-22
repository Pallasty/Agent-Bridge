# Main Recall Case #2 Tool-Surface Negative Controls

Date: 2026-06-22
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `0d785b8` (`test(memory): probe case2 tool surface projection`)
Scope: eval-only diagnostic/probe

## Why

The previous case #2 probe recovered the designated tool-surface taxonomy memory
at accepted rank 2, but it also showed two risks:

- the top accepted result can be a same-policy memory rather than the designated
  taxonomy reference;
- the accepted set included `work_memory_*_precompact` scratchpad rows.

This slice tests whether the projection is over-broad before any runtime design
is considered.

## Change

`crates/bridge/examples/recall_eval.rs` now prints:

```text
## Case #2 tool-surface negative controls
```

The probe remains scratch-only. It adds:

- six negative controls covering generic tool-use help, tool latency triage, MCP
  diagnostic errors, git/sibling worktree operations, `memory_search` quality,
  and a single profile/tool vocabulary query;
- a durable accepted view for case #2 that filters volatile candidate keys:
  `work_memory_*`, `snapshot_*`, and `alert_*`;
- unit coverage for latency/diagnostic negatives, single-profile-threshold
  behavior, and prefix-scoped `work_memory_` detection.

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo run -p ab-bridge --example recall_eval
cargo check -p ab-bridge --all-targets
```

All commands passed. The Rust commands emitted existing warnings in
`ab-store`/`mcp_tools.rs`; this slice added no new failure.

Current output:

```text
## Case #2 tool-surface projection probe
  toolproj hit: 2  toolproj_acc hit: 2  toolproj_acc_durable hit: 2
  contamination: accepted_work_memory=2 durable_work_memory=0
```

The durable accepted top still recovers the expected memory at rank 2 while
removing the two `work_memory_*` rows:

| rank | overlap | key | read |
|---:|---:|---|---|
| 1 | 5 | `goal_b_surface_growth_gate_engine_finding_20260621` | same policy cluster |
| 2 | 5 | `reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618` | expected hit |
| 3 | 4 | `tool_diagnostics_plan_load_lookup_miss_20260619` | tool diagnostics distractor |
| 4 | 4 | `mcp_codex_native_overlap_surface_narrowed_deployed_20260617` | overlap/surface distractor |
| 5 | 4 | `goal_c_recall_eval_falsifier_anchor_contribution_20260621` | recall-eval distractor |

Negative controls:

| control | projection terms | accepted | durable | target hits | work_memory hits |
|---|---|---:|---:|---:|---:|
| `generic_tool_use` | none | 0 | 0 | 0 | 0 |
| `tool_latency_sample` | none | 0 | 0 | 0 | 0 |
| `mcp_diagnostic_error` | none | 0 | 0 | 0 | 0 |
| `git_sibling_worktree` | none | 0 | 0 | 0 | 0 |
| `memory_search_quality` | none | 0 | 0 | 0 | 0 |
| `profile_missing_tool` | `projtoolprofiletier`, `projtoolretier` | 0 | 0 | 0 | 0 |

Summary:

```text
controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0
```

The standard runtime gate remains unchanged and separately reported:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
```

## Read

The projection survived this first negative-control slice:

- generic tool-use and operational diagnostics do not cross the accepted
  projection threshold;
- a profile/tool query produces only two projection terms, below the required
  four-term gate;
- durable filtering removes the scratchpad contamination without losing the
  expected #2 memory.

The result is still not a runtime authorization:

- the designated reference is rank 2, not rank 1;
- nonvolatile distractors remain in the top set;
- the negative set is small and hand-curated.

## Next Gate

Recommended next slice:

```text
main-recall-case2-tool-surface-positive-controls-v1
```

The positive-control slice should decide whether the projection generalizes
inside the intended family:

1. paraphrase variants of "tool surface too large / classify / contract / delete
   vs re-tier";
2. English variants using `tool surface`, `taxonomy`, `retier`, and `delete`;
3. near-positive queries about tool profile/tier policy that should return the
   same policy cluster;
4. a stricter accepted mode that requires `projtoolsurface` plus at least three
   additional policy terms, not just any four projection terms.

Only after positive controls and stricter acceptance pass should a runtime
candidate-expansion design be considered.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, or deploy
behavior.
