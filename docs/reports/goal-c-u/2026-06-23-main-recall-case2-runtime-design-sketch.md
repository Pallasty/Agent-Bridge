# Main Recall Case #2 Runtime Design Sketch

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `2d64f36` (`docs(memory): adjudicate case2 tool surface ranks`)
Scope: design-only; no runtime implementation

## Why

The case #2 tool-surface path has now passed three gates:

1. negative controls: generic tool-use, latency, MCP diagnostics, git/worktree,
   `memory_search` quality, and weak profile wording do not cross accepted
   projection;
2. positive controls: 11/11 intended tool-surface policy queries recover the
   target family in strict durable mode;
3. rank adjudication: recurring candidates are now typed as primary answer,
   same-policy cluster, adjacent subcase, or diagnostic/meta distractor.

This report sketches the smallest plausible production design that could be
implemented next. It is intentionally not an implementation authorization.

## Inputs

Pinned baseline identity:

```text
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313
```

Current pinned hard-tier anchor:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
hard fts misses: #1, #2, #8, #9, #14
hard zero-row fts misses: #1, #2
```

Case #2 strict candidates:

```text
primary:       reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618
same-policy:   goal_b_surface_growth_gate_engine_finding_20260621
adjacent:      mcp_codex_native_overlap_surface_narrowed_deployed_20260617
exclude:       tool_diagnostics_plan_load_lookup_miss_20260619
exclude:       goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

## Proposed Runtime Shape

### Trigger Condition

Do not run projected expansion for every search.

The first production candidate should trigger only when all are true:

- retrieval mode is FTS-like, not semantic-only;
- baseline FTS returns zero rows, or the query matches a narrow hard-miss
  diagnostic cohort in `recall_eval`;
- query projection emits `projtoolsurface` plus at least three additional
  tool-surface policy terms;
- the caller asks for normal memory recall, not diagnostics over tool errors or
  plan lookup state.

For case #2 specifically, this means the path is eligible because the pinned
baseline is a zero-row FTS miss and the query projects to:

```text
projtoolsurface, projtooltaxonomy, projtoolcontraction, projtooldelete, projtoolretier
```

### Candidate Source

Keep baseline FTS as the authority when it returns usable rows. For eligible
misses, assemble a bounded projected candidate set:

1. start with any baseline FTS rows, preserving order;
2. append projected candidates from an FTS side table or equivalent generated
   projection index;
3. require durable row hygiene: exclude `work_memory_`, `snapshot_`, `alert_`,
   `skill:`, archived/superseded rows, and non-active memories;
4. cap projected additions tightly, for example top 5-8 rows before final
   scoring;
5. emit debug evidence in `recall_eval` before using the path in live MCP.

The projected index can be scratch-only until the gate passes. A production
index should be introduced only after the before/after eval shows hard-tier
movement without negative-control regressions.

### Role-Aware Candidate Policy

The rank-adjudication result argues against treating all strict candidates as
equal. The candidate role should be explicit:

| role | expected behavior |
|---|---|
| `primary_answer` | eligible to satisfy the original query and outrank cluster/context rows |
| `same_policy_cluster` | useful as second result or context; may satisfy broader policy queries |
| `adjacent_subcase` | demote unless query contains subcase anchors such as Codex/native overlap/profile/codebase |
| `diagnostic_or_meta` | exclude from case #2 expansion unless query explicitly asks for diagnostics, recall-eval, or Goal C governance |

For the first implementation sketch, roles can be rule-derived:

- primary: contains `projtoolsurface`, `projtooltaxonomy`, and at least one of
  `projtoolcontraction`, `projtooldelete`, `projtoolretier`;
- same-policy cluster: also matches the policy cluster but has broader Goal B /
  gate-growth vocabulary;
- adjacent subcase: contains Codex/native-overlap/profile/codebase anchors not
  present in the query;
- diagnostic/meta: contains diagnostics, Tool Atlas, Event Spine, plan lookup,
  recall-eval, falsifier, or Goal C governance anchors not present in the query.

This rule set should live in the eval probe first. If it works, production can
reuse the same role labels or a simplified equivalent.

### Ranking Contract

For an eligible zero-row/hard-miss query:

1. return primary-answer projected candidates before same-policy context;
2. keep same-policy context visible but do not let it bury the primary taxonomy
   answer;
3. demote adjacent subcases unless the query explicitly names their anchors;
4. exclude diagnostic/meta rows unless the query asks for that diagnostic/meta
   domain;
5. never reorder ordinary baseline FTS rows for queries that already return
   non-empty FTS results.

The intended case #2 outcome is:

```text
rank 1: reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618
rank 2: goal_b_surface_growth_gate_engine_finding_20260621
optional later: mcp_codex_native_overlap_surface_narrowed_deployed_20260617 only if subcase anchors match
excluded: tool_diagnostics_plan_load_lookup_miss_20260619
excluded: goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

## Eval Gate Before Production

Before any production retrieval change, add an eval-only candidate assembler to
`recall_eval` and require:

```text
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db \
  cargo run -p ab-bridge --example recall_eval
```

Minimum pass criteria:

- store fingerprint is unchanged: `pinned=true active=3022 edges=5527
  newest=1782205313`;
- hard-tier FTS-like projected mode improves case #2 without regressing #1/#8/#9/#14;
- case #2 target reaches rank 1 or at least outranks same-policy and diagnostic
  candidates in the projected mode;
- six negative controls remain empty accepted sets;
- eleven positive controls retain `strict_hits=11` and `strict_empty=0`;
- diagnostic/meta rows stay excluded for generic tool-surface queries;
- full report prints before/after hard-tier R@10 alongside case-level ranks.

No runtime-lift claim should be accepted from live-store-only output.

## Implementation Boundary

If this design is accepted, the next implementation should still be staged:

1. eval-only role-aware assembler in `recall_eval`;
2. frozen before/after report;
3. production design review;
4. guarded production implementation behind a feature flag or narrow mode;
5. MCP/live verification after reconnect.

This slice stops at step 0: design. It does not change production search,
schema, indexing, ranking, graph expansion, semantic retrieval, MCP surfaces,
memory rows, deployment, or the pinned snapshot.

## Open Questions

- Whether the projected role labels should be stored, derived at query time, or
  remain eval-only until more cases are covered.
- Whether the first production candidate should cover only zero-row misses or
  also nonzero verified hard misses.
- Whether #1/#8/#9/#14 need separate projection families before any shared
  runtime mechanism is worth implementing.
- Whether a read-only snapshot-open path is required before production gate
  claims, given the current WAL behavior documented in the frozen-baseline
  report.
