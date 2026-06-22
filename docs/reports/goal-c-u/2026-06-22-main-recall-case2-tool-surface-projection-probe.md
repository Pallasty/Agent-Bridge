# Main Recall Case #2 Tool-Surface Projection Probe

Date: 2026-06-22
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `0543f6e` (`docs(memory): autopsy main recall hard misses`)
Scope: eval-only diagnostic/probe

## Why

The hard-miss autopsy in `2026-06-22-main-recall-hard-miss-autopsy.md`
classified main `recall_eval` case #2 as a candidate-visibility failure:

```text
工具面太多了应该按什么维度归类收口,是直接删还是重新分级
```

Expected memory:

```text
reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618
```

Baseline FTS and hybrid returned no expected hit. The CJK empty-fallback probe
also did not recover #2, which means plain CJK text visibility is not enough.
This probe tests one narrower hypothesis:

> If both query and candidate text are projected onto explicit tool-surface
> concepts, can the expected memory become visible without touching production
> search?

## Change

`crates/bridge/examples/recall_eval.rs` now prints one extra read-only diagnostic
block:

```text
## Case #2 tool-surface projection probe
```

The probe builds an in-memory SQLite FTS table from the read-only memory store
and augments only that scratch table with canonical projection tokens such as:

- `projtoolsurface`
- `projtooltaxonomy`
- `projtoolcontraction`
- `projtoolretier`
- `projtooldelete`
- `projtoolprofiletier`
- `projtoolverifyfirst`

Accepted mode requires at least four shared projection terms between the query
and candidate memory. The implementation also adds unit tests that:

- bridge the case #2 Chinese query;
- bridge the expected tool-surface taxonomy memory;
- reject a generic tool-use query.

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo run -p ab-bridge --example recall_eval
cargo check -p ab-bridge --all-targets
```

Results:

```text
## Case #2 tool-surface projection probe
  query terms: projtoolcontraction, projtooldelete, projtoolretier,
    projtoolsurface, projtooltaxonomy
  toolproj hit: 2  toolproj_acc hit: 2
```

All commands passed. The Rust commands emitted existing warnings in
`ab-store`/`mcp_tools.rs`; this slice added no new failure.

Accepted top:

| rank | overlap | key | read |
|---:|---:|---|---|
| 1 | 5 | `goal_b_surface_growth_gate_engine_finding_20260621` | same topic, but not the designated #2 reference |
| 2 | 5 | `reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618` | expected hit |
| 3 | 4 | `tool_diagnostics_plan_load_lookup_miss_20260619` | tool diagnostics distractor |
| 4 | 4 | `mcp_codex_native_overlap_surface_narrowed_deployed_20260617` | overlap/surface distractor |
| 5 | 4 | `goal_c_recall_eval_falsifier_anchor_contribution_20260621` | recall-eval distractor |
| 6 | 4 | `work_memory_3d56857a5eed_019e4467-964c-7ed0-b7cb-9bdc83a8aba4_precompact` | scratchpad contamination |
| 7 | 4 | `work_memory_417d88062270_019e660b-f37a-7770-8b92-11d5aa342327_precompact` | scratchpad contamination |

The standard `recall_eval` production-mode rows remain separately reported. This
probe does not add a new production metric row and does not claim that live
`memory_search` improved.

## Read

The hypothesis is partially validated:

- #2 is recoverable when the query and candidate are projected onto
  tool-surface taxonomy concepts.
- The failure is therefore not merely missing data and not primarily graph
  traversal.
- Plain CJK shingling was too lexical; the missing bridge is conceptual and
  domain-specific.

The hypothesis is also constrained:

- The expected memory is rank 2, not rank 1.
- The accepted top set includes plausible but non-designated tool-surface
  memories.
- The accepted top set includes `work_memory_*` scratchpad rows, which is a
  contamination signal for any runtime candidate-set design.

So this is a candidate-visibility proof, not a runtime retrieval proposal.

## Next Gate

A future runtime proposal must clear at least these controls before this idea is
eligible for live retrieval:

1. Keep the probe eval-only until a broader control set exists.
2. Add negative controls for generic tool-use, tool latency, and MCP diagnostic
   queries so tool-surface projection does not overmatch unrelated tool traffic.
3. Exclude or demote scratchpad/work-memory rows unless the user explicitly asks
   for active scratch context.
4. Decide whether `goal_b_surface_growth_gate_engine_finding_20260621` is a
   legitimate also-correct answer or a distractor before treating rank 2 as a
   ranking failure.
5. Compare with a smaller alias/projection dictionary before adding more
   canonical tokens.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, or deploy
behavior.

Recommended next slice:

```text
main-recall-case2-tool-surface-negative-controls-v1
```

That slice should decide whether the projection can survive hard negatives and
work-memory contamination before any runtime candidate expansion is designed.
