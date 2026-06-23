# Main Recall Case #2 Tool-Surface Rank Adjudication

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `f398cb4` (`fix(c3): explain s2 retired credit in alerts`)
Scope: eval/report-only adjudication

## Why

The case #2 projection now passes negative and positive controls, but strict
candidates still contain recurring nonvolatile near-misses. Before designing a
runtime candidate-expansion path, those rows need content adjudication:

> Which candidates are also-correct, which are same-cluster but not primary, and
> which are diagnostic noise?

This report reads the pinned snapshot directly with SQLite, not `memory_get`, so
it does not bump live memory access counters.

Pinned context:

```text
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313
```

## Observed Strict Candidate Shape

Pinned `recall_eval` case #2 strict accepted output:

```text
1. overlap=5 goal_b_surface_growth_gate_engine_finding_20260621
2. overlap=5 reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618 <== EXPECTED
3. overlap=4 mcp_codex_native_overlap_surface_narrowed_deployed_20260617
4. overlap=4 tool_diagnostics_plan_load_lookup_miss_20260619
5. overlap=4 goal_c_recall_eval_falsifier_anchor_contribution_20260621
```

The positive controls remain healthy:

```text
controls=11 durable_hits=11 strict_hits=11 strict_cluster_hits=11 strict_empty=0
```

Rank pattern across the 11 positive controls:

| candidate | pattern | read |
|---|---|---|
| `reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618` | always top 3; rank 1 on 3 controls | primary taxonomy answer remains reliably visible |
| `goal_b_surface_growth_gate_engine_finding_20260621` | often rank 1; same cluster hit on every control | same policy cluster, often fresher/strategic |
| `mcp_codex_native_overlap_surface_narrowed_deployed_20260617` | common top-3 adjacent row | narrower Codex/native-overlap subcase |
| `tool_diagnostics_plan_load_lookup_miss_20260619` | intermittent top-3 row | diagnostic/tool-atlas context, not a case #2 answer |
| `goal_c_recall_eval_falsifier_anchor_contribution_20260621` | appears in original case #2 strict set | meta recall-eval/falsifier context, not a case #2 answer |

## Content Adjudication

| key | verdict | rationale |
|---|---|---|
| `reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618` | primary answer | Directly answers the original question: classify the Agent-Bridge tool surface by trigger pattern, prefer verify-first, and decide re-tier over delete. It contains the 8-class taxonomy and shipped cleanup details. |
| `goal_b_surface_growth_gate_engine_finding_20260621` | same-policy cluster, not a false positive | This is a later strategic finding: tool-surface growth is now driven by gate/tool proliferation, so the leverage is stopping incremental exposure rather than more cleanup. It links to the taxonomy reference and answers the broader "too many tools, delete vs re-tier" concern. It should count as cluster evidence, but not replace the taxonomy reference when the query asks for classification dimensions. |
| `mcp_codex_native_overlap_surface_narrowed_deployed_20260617` | adjacent subcase | This is a real deployed re-tier decision for Codex native-overlap tools. It is also-correct for the separate corpus case about Codex/native overlap, and useful as an example, but too narrow for generic case #2. It should be demoted unless the query mentions Codex, native overlap, essential profile, or codebase tools. |
| `tool_diagnostics_plan_load_lookup_miss_20260619` | diagnostic distractor | This row classifies an expected `plan_load` lookup miss in Tool Atlas/Event Spine diagnostics. It contains tool/profile/design-board vocabulary but does not answer taxonomy, contraction, delete, or re-tier policy. It should not be accepted for case #2. |
| `goal_c_recall_eval_falsifier_anchor_contribution_20260621` | meta-governance distractor | This row discusses Goal C recall-eval as a continuity falsifier and mentions D2 tool-surface metastasis. It explains why the tool-surface problem matters, not what taxonomy or re-tier action to use. It should stay out of the case #2 answer set. |

## Decision

Do not treat "strict candidate" as a single runtime-acceptance bucket. The
strict set needs typed interpretation:

1. **Primary answer**: target taxonomy reference.
2. **Same-policy cluster**: `goal_b_surface_growth_gate_engine_finding_20260621`.
3. **Adjacent subcase**: `mcp_codex_native_overlap_surface_narrowed_deployed_20260617`.
4. **Diagnostic/meta distractors**: `tool_diagnostics_plan_load_lookup_miss_20260619`
   and `goal_c_recall_eval_falsifier_anchor_contribution_20260621`.

The right runtime-design implication is not "append all strict candidates." It
is:

- keep the current exact/FTS ordering as baseline;
- add a guarded expansion path only for zero-row or verified hard-miss cases;
- score or label projected candidates by role, so primary taxonomy and
  same-policy rows outrank adjacent subcases, and diagnostic/meta rows are
  excluded or heavily demoted;
- preserve a separate cluster-hit metric instead of expanding the accept-set
  until same-cluster rows are content-approved for the specific query shape.

## Next Gate

Recommended next slice:

```text
main-recall-case2-runtime-design-sketch-v1
```

That slice should write a runtime design without implementation authority:

- trigger condition: zero-row FTS or pinned hard miss, not every query;
- candidate source: existing FTS plus bounded projected candidates;
- rank policy: primary > same-policy cluster > adjacent subcase > diagnostic/meta
  excluded;
- observability: print before/after against the pinned `AB_BASELINE_DB`
  fingerprint and preserve hard-tier gate reporting.

Only after that design is reviewed should any production retrieval code be
changed.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, deploy
behavior, or the pinned snapshot. It only adjudicates the case #2 strict
candidates and narrows the next runtime-design path.
