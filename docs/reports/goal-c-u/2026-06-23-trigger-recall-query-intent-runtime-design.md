# Trigger Recall Query-Intent Runtime Design - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Worktree: `/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge`

Base: `9203041` (`test(memory): add trigger continuation intent gate`)

Scope: design-only; no runtime implementation

## Why

The AIO2-native trigger recall line now has a useful but still eval-only shape:

| Slice | Result |
|---|---|
| `projected_union` | recovers the known G25 and Goal C dashboard/state misses |
| `union+policy` | removes write-bypass and creative non-continuation false hits |
| `union+cont` | removes the remaining frontend/health dashboard-state false hits |

Latest eval evidence from
`docs/reports/goal-c-u/2026-06-23-trigger-recall-aio2-continuation-intent-gate.md`:

| Mode | R@10 | MRR | Misses | False Hits |
|---|---:|---:|---:|---:|
| `projected_union` | 1.000 | 0.857 | 0 | 22 |
| `union+policy` | 1.000 | 0.857 | 0 | 4 |
| `union+cont` | 1.000 | 0.857 | 0 | 0 |

The design question is no longer whether broad projected assembly can recover
the local miss. It can. The question is where a query-intent acceptance layer
could sit without changing default `memory_search` behavior or turning a
corpus-local rule into production authority too early.

## Current Runtime Anchor

Current `memory_search` behavior in `crates/bridge/src/mcp_tools.rs` is:

1. parse `query`, `tags_any`, `limit`, `mode`, `scope`, `scope_mode`, and
   `exclude_kinds`;
2. call one of:
   - `store.memory_search_hybrid(...)`;
   - `store.memory_search_semantic(...)`;
   - `store.memory_search(...)`;
3. apply scope filtering/fallback;
4. apply Seed boost;
5. apply coactivation rerank;
6. record coactivation traces for top visible hits;
7. apply `exclude_kinds`, truncate to requested `limit`, log telemetry, and
   return JSON.

The eval-only trigger harness is separate. `trigger_recall_eval` builds
scratch FTS tables and tests:

```text
projected_union -> policy gate -> continuation-intent gate
```

None of that path is currently connected to production `memory_search`.

## Proposed Runtime Shape

### Trigger Condition

Do not run trigger/projected expansion for normal searches.

The first production candidate should be reachable only through an explicit
opt-in path after another eval/report gate. Minimum trigger conditions:

- retrieval mode is `fts`;
- caller opts into trigger/projected recall, not default `memory_search`;
- a local project scope is present and resolved before expansion;
- baseline FTS has a known recall weakness for the query family, or the query
  matches a small accepted trigger-recall cohort;
- the active regression corpus has passed with unchanged or better
  `union+cont` metrics.

Non-goals for the first runtime candidate:

- no default `mode=fts` behavior change;
- no `mode=hybrid` or `mode=semantic` integration;
- no graph/PageRank or semantic signal in the acceptance decision;
- no global query policy that suppresses ordinary baseline search results.

### Candidate Source

The query-intent layer should gate only supplemental trigger/projected
candidates.

Recommended order for an explicit opt-in prototype:

1. run baseline FTS as today;
2. build a bounded supplemental projected/trigger candidate set;
3. run query-intent acceptance before supplemental candidates join the visible
   page;
4. merge accepted supplemental candidates with baseline hits;
5. apply the normal downstream scope/boost/rerank/output path only to the final
   eligible set.

If the query-intent gate rejects the query, the system should drop only the
supplemental projected candidates and return the baseline FTS results. It
should not return an empty result solely because a dashboard/state query was
classified as frontend or health intent.

### Acceptance Layer

The acceptance layer should have two independent decisions:

| Layer | Purpose | Example Reject Reason |
|---|---|---|
| policy/adversarial gate | prevent write-bypass or creative non-continuation queries from accepting project-state candidates | `write_bypass_intent`, `creative_non_continuation_intent` |
| continuation-intent gate | separate legitimate project continuation from unrelated dashboard/state domains | `frontend_dashboard_intent`, `health_dashboard_intent` |

Both layers should be deterministic, explainable, and audit-emitting in the
first runtime candidate. If a later classifier is considered, it should first
emit side-by-side decisions against these rule labels in eval mode.

## Allowed Signals

Allowed in the first runtime candidate:

- normalized query text;
- retrieval mode and explicit opt-in flag;
- requested scope and scope relation after local scope resolution;
- query-level lexical features already proven in eval controls;
- candidate source label such as `baseline_fts` or `projected_union`;
- candidate count and rank positions;
- gate version and reject reason.

Not allowed in the first runtime candidate:

- graph centrality/PageRank/coactivation as acceptance evidence;
- semantic embeddings or external LLM classification;
- memory writes, memory_get side effects, or access-count side effects;
- raw memory content inspection beyond already assembled candidate metadata;
- global policy that changes ordinary baseline `memory_search`;
- hidden expansion in default `fts`, `hybrid`, or `semantic` modes.

## Audit Contract

Every explicit opt-in run should emit a compact audit object before production
use is considered. The audit should avoid raw query or raw memory content unless
the caller explicitly asks for diagnostics.

Suggested shape:

```json
{
  "schema": "agent_bridge.memory.trigger_query_intent_acceptance.v0",
  "enabled": true,
  "mode": "fts",
  "default_memory_search_unchanged": true,
  "scope_mode": "local_only",
  "candidate_source": "projected_union",
  "query_hash": "sha256:...",
  "policy_gate": {
    "decision": "allow",
    "reject_reason": null
  },
  "continuation_gate": {
    "decision": "reject",
    "reject_reason": "frontend_dashboard_intent"
  },
  "supplemental_candidates_before_gate": 10,
  "supplemental_candidates_after_gate": 0,
  "fallback_behavior": "baseline_fts_only",
  "regression_anchor": "aio2_trigger_recall_union_cont_20260623"
}
```

If the gate allows a query, the audit should still include the gate version,
the accepted supplemental count, and the regression anchor. That keeps "allowed"
from becoming invisible behavior.

## Regression Controls

The following controls should become permanent before runtime implementation:

Positive continuation cases:

| Case | Expected |
|---|---|
| `aio2_goal_c_dashboard_state_boundary` | Goal C boundary memory remains accepted |
| `aio2_goal_c_dashboard_state_closure` | Goal C closure memory remains accepted |
| `aio2_lswr_g25_store_write` | G25 projected miss remains recovered by projected union |
| `aio2_ghp1b_tiny_write_packet` | Legitimate dry-run/materialization continuation remains accepted |

Policy/adversarial rejects:

| Control | Expected Reason |
|---|---|
| `aio2_adjacent_write_request` | `write_bypass_intent` |
| `aio2_adjacent_zh_write_bypass` | `write_bypass_intent` |
| `aio2_adjacent_lswr_poetry` | `creative_non_continuation_intent` |
| `aio2_adjacent_zh_lswr_poetry` | `creative_non_continuation_intent` |

Continuation/domain rejects:

| Control | Expected Reason |
|---|---|
| `aio2_unrelated_frontend` | `frontend_dashboard_intent` |
| `aio2_unrelated_frontend_goal_c_words` | `frontend_dashboard_intent` |
| `aio2_unrelated_controlled_rsi_health_dashboard` | `health_dashboard_intent` |

Minimum eval gate before implementation:

```bash
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Required result:

- corpus ready is true;
- `union+cont` R@10 remains 1.000;
- `union+cont` misses remain 0;
- `union+cont` false hits remain 0 on the current control set;
- all explicit policy/continuation reject reasons match the tables above;
- no parser errors;
- no production retrieval path is changed by the eval run.

## Implementation Boundary

If this design is accepted, the next implementation should still be staged:

1. add an eval-only runtime-shaped assembler that models baseline plus
   supplemental projected candidates and prints the audit object;
2. freeze the regression controls and expected reject reasons in tests;
3. write a production review packet comparing baseline-only vs opt-in
   supplemental behavior;
4. only then consider an explicit opt-in runtime path;
5. keep default `memory_search` unchanged until a later, separate authorization.

This report stops at design. It does not change production search, schema,
indexing, ranking, graph expansion, semantic retrieval, MCP surfaces, memory
rows, deployment, or GHP materialization.

## Open Questions

- Whether the first opt-in surface should be a separate diagnostic tool or an
  internal feature flag inside `memory_search`.
- Whether the accepted projected/trigger candidate source should come from a
  persistent side table, a regenerated scratch index, or a store-backed
  projection field.
- Whether scope filtering should happen before supplemental assembly or be
  re-applied both before and after merge.
- Whether future non-English dashboard/state controls should extend the same
  deterministic rules or wait for a larger classifier comparison.
