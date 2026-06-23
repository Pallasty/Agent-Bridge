# Main Recall Case #2 Eval Assembler

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `66fc093` (`docs(memory): sketch case2 runtime retrieval design`)
Scope: eval-only; no runtime implementation

## Why

The case #2 runtime design sketch requires one more proof before production
review: the proposed role-aware policy must work inside `recall_eval` against
the pinned snapshot without changing production retrieval.

This slice implements that assembler only in the eval harness. It verifies the
ranking policy:

```text
primary answer > same-policy cluster > adjacent subcase; diagnostic/meta excluded by default
```

## What Changed

`crates/bridge/examples/recall_eval.rs` now has an eval-only role-aware
projected candidate assembler:

- it starts from strict durable projected candidates;
- labels each candidate as `primary`, `same-policy`, `adjacent`,
  `diagnostic-meta`, or `other`;
- excludes diagnostic/meta candidates unless the query explicitly asks for that
  diagnostic/meta domain;
- sorts by role first, then overlap, then key for deterministic output;
- prints role-aware case #2 and positive-control evidence.

This is not connected to `SqliteStore::memory_search`, MCP `memory_search`,
schema, tokenizer, graph, semantic search, or live runtime ranking.

## Pinned Context

Command:

```sh
AB_BASELINE_DB="$HOME/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db" \
  cargo run -p ab-bridge --example recall_eval
```

Harness identity:

```text
baseline db source: AB_BASELINE_DB (caller-pinned DB)
store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313
embed backend: multilingual-e5-small
```

## Case #2 Result

Before role-aware sorting, the strict durable candidate family still has the
primary answer at rank 2:

```text
toolproj hit: 2  toolproj_acc hit: 2  toolproj_acc_durable hit: 2  role_aware hit: 1
```

Durable accepted top:

```text
1. goal_b_surface_growth_gate_engine_finding_20260621
2. reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618 <== EXPECTED
3. mcp_codex_native_overlap_surface_narrowed_deployed_20260617
4. tool_diagnostics_plan_load_lookup_miss_20260619
5. goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

Role-aware strict durable top:

```text
1. role=primary reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618 <== EXPECTED
2. role=same-policy goal_b_surface_growth_gate_engine_finding_20260621
3. role=adjacent mcp_codex_native_overlap_surface_narrowed_deployed_20260617
```

Diagnostic/meta rows are excluded from the generic tool-surface query:

```text
tool_diagnostics_plan_load_lookup_miss_20260619
goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

## Controls

Negative controls stayed clean:

```text
controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0
```

Positive controls stayed healthy and improved at the role-aware layer:

```text
controls=11 durable_hits=11 strict_hits=11 strict_cluster_hits=11 strict_empty=0 role_aware_hits=11 role_aware_rank1_hits=11
```

That means every positive-control query still reaches the target family, and
the role-aware assembler places the primary taxonomy answer at rank 1 in all 11
positive controls.

## Hard-Tier Read

The standing hard-tier runtime anchor remains unchanged because this assembler
is not wired into any production or aggregate retrieval mode:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
hard fts misses: #1, #2, #8, #9, #14
hard zero-row fts misses: #1, #2
```

This is the intended interpretation. The eval assembler proves a candidate
case-level policy for #2; it does not claim production recall lift.

## Tests

```text
cargo test -p ab-bridge --example recall_eval -- --nocapture
20 passed; 0 failed
```

New unit coverage:

- primary answer outranks same-policy and adjacent candidates;
- diagnostic/meta candidates are excluded by default;
- diagnostic/meta candidates can be included when the query explicitly asks for
  the diagnostic/meta domain.

## Decision

The role-aware assembler passes the eval-only gate for case #2:

- it fixes the case #2 target rank inside projected strict durable candidates;
- it preserves negative controls;
- it preserves all positive-control hits;
- it makes the primary answer consistently rank 1 across the positive-control
  suite;
- it keeps production retrieval untouched.

## Next Gate

Recommended next slice:

```text
main-recall-case2-production-review-packet-v1
```

That packet should decide whether the production candidate should be:

1. rejected as too narrow for runtime despite eval success;
2. kept as eval-only until more hard cases have projection families; or
3. implemented behind an explicit narrow runtime flag or opt-in mode.

Do not wire this into default `memory_search` directly from this report. The
snapshot-open mutability/WAL caveat in the frozen-baseline report still argues
for one more production review and possibly a read-only store-open hardening
slice before live retrieval behavior changes.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, deploy
behavior, or the pinned snapshot. It only extends `recall_eval` and documents
the case #2 eval result.
