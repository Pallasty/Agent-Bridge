# GHP-1c Related Keys Materialization

Date: 2026-07-01

Status: `TINY_WRITE_APPLIED / BACKED_UP / POSTCHECKED`

## Decision

Apply the first tiny `related_keys` graph-hygiene write packet.

This packet materialized ten exact-scope Agent-Bridge `related_keys`
relationships into explicit `memory_edges` rows with `edge_type='relates'` and
`weight=1.0`.

The write followed the read-only audits:

- `docs/reports/goal-c-u/2026-07-01-memory-graph-hygiene-audit.md`
- `docs/reports/goal-c-u/2026-07-01-memory-graph-hygiene-readonly-audit.md`

It does not approve PageRank, centrality ranking, automatic orphan linking, or
any retrieval-order change.

## Pre-Write State

Repo head before the write:

```text
4f91acb docs(memory): audit graph hygiene read-only
worktree=clean master...origin/master
```

SQLite pre-check:

```text
PRAGMA quick_check=ok
```

SQLite backup:

```text
source=/home/pallasting/.local/share/agent-bridge/state.db
backup=/home/pallasting/.local/share/agent-bridge/backups/state.before-ghp1c-related-keys-materialize.20260701T200040Z.db
size=192262144
sha256=3dfe1c982dd0e2548a1fa745c149adb709a73ac00ebd75d7ec0a8ccd4a8a67b9
```

## Write Contract

Writer:

```text
memory_related_keys_materialize
```

Arguments:

```text
dry_run=false
apply_confirmation=materialize_related_keys
scope=project:/Data/CascadeProjects/agent-bridge
scope_mode=local_only
scope_filter=exact
selection_strategy=orphan_reduction
max_edges=10
max_records=1500
edge_type=relates
weight=1.0
dedupe_undirected_pairs=true
require_scope_compatible=true
max_inbound_per_target=3
max_outbound_per_source=3
skip_kinds=[alert, work_memory, snapshot, feedback, skill, present_outcome]
skip_tags=[auto_curated, implicit, unverified_identifier, alert, ttl:7d,
ttl:14d, ttl:30d, ttl:45d, source:precompact]
```

Dry-run immediately before the write:

```text
blocked=false
selected_edges=10
linked=0
write_errors=[]
current_orphans=10
orphans_reduced_by_selected=4
projected_orphans_after_selected=6
```

Live write result:

```text
blocked=false
linked=10
write_errors=[]
created_at=1782936089
```

## Materialized Edges

| From | To |
|---|---|
| `agent_bridge_scope_canonical_host_policy_packet_20260625` | `agent_bridge_scope_phase3_aio2_dryrun_20260625` |
| `agent_bridge_open_queue_audit_20260701` | `centrality_prior_offline_no_go_repo_record_20260701` |
| `correction_cosurface_single_edge_backfill_done_20260701` | `centrality_prior_offline_no_go_repo_record_20260701` |
| `memory_graph_hygiene_readonly_audit_20260701` | `centrality_prior_offline_no_go_repo_record_20260701` |
| `decision_ab_gte_runtime_switch_plan_closed_20260630` | `decision_ab_borrowed_patterns_workspace_boundary_plan_complete_20260630` |
| `decision_borrow_landing_outcomes_20260628` | `decision_borrowed_patterns_cascade_scan_20260628` |
| `decision_borrow_landing_outcomes_20260628` | `todo_t1_side_signal_scorer_sharpen_20260628` |
| `decision_borrow_landing_outcomes_20260628` | `todo_t2_quant_draft_unverified_20260628` |
| `decision_t5_columnar_landed_new_crate_20260628` | `decision_borrow_landing_outcomes_20260628` |
| `decision_ab_borrowed_patterns_workspace_boundary_plan_complete_20260630` | `decision_ab_tombstone_export_filter_verified_20260630` |

Each selected row was read back from `memory_edges` with:

```text
edge_type=relates
weight=1.0
created_at=1782936089
```

## Post-Write Checks

SQLite:

```text
PRAGMA quick_check=ok
```

Exact topology with the same durable-project filters used in the P1 audit:

| Metric | Before P1 audit | After GHP-1c |
|---|---:|---:|
| non-skill active total | 355 | 357 |
| orphan count | 17 | 14 |
| orphan fraction | 0.048 | 0.039 |
| P4 evolved coverage | 300 | 302 |
| P4 evolved fraction | 0.845 | 0.846 |
| top hub degree | 37 | 37 |
| top hub fraction | 0.104 | 0.104 |

`memory_related_keys_preflight` with the stricter generated/noisy exclusions:

| Metric | Before write | After write |
|---|---:|---:|
| current edge pairs | 1072 | 1082 |
| safe candidate pairs | 343 | 333 |
| current orphans | 17 | 14 |
| orphan candidate nodes | 14 | 11 |
| projected orphans after candidates | 3 | 3 |

`memory_related_keys_review_packet` with exact-scope orphan-reduction selection:

| Metric | Before write | After write |
|---|---:|---:|
| current edge pairs | 1035 | 1045 |
| current orphans | 10 | 6 |
| selected edges for next packet | 10 | 10 |
| orphans reduced by next selected | 4 | 2 |
| projected orphans after next selected | 6 | 4 |

## Rollback

Primary rollback can delete exactly the ten inserted edges:

```sql
DELETE FROM memory_edges
WHERE edge_type='relates'
  AND (from_key, to_key) IN (
    ('agent_bridge_scope_canonical_host_policy_packet_20260625','agent_bridge_scope_phase3_aio2_dryrun_20260625'),
    ('agent_bridge_open_queue_audit_20260701','centrality_prior_offline_no_go_repo_record_20260701'),
    ('correction_cosurface_single_edge_backfill_done_20260701','centrality_prior_offline_no_go_repo_record_20260701'),
    ('memory_graph_hygiene_readonly_audit_20260701','centrality_prior_offline_no_go_repo_record_20260701'),
    ('decision_ab_gte_runtime_switch_plan_closed_20260630','decision_ab_borrowed_patterns_workspace_boundary_plan_complete_20260630'),
    ('decision_borrow_landing_outcomes_20260628','decision_borrowed_patterns_cascade_scan_20260628'),
    ('decision_borrow_landing_outcomes_20260628','todo_t1_side_signal_scorer_sharpen_20260628'),
    ('decision_borrow_landing_outcomes_20260628','todo_t2_quant_draft_unverified_20260628'),
    ('decision_t5_columnar_landed_new_crate_20260628','decision_borrow_landing_outcomes_20260628'),
    ('decision_ab_borrowed_patterns_workspace_boundary_plan_complete_20260630','decision_ab_tombstone_export_filter_verified_20260630')
  );
```

Full rollback can instead restore the SQLite backup listed above.

## Boundary

This packet did not:

- write or delete durable memory rows;
- modify `related_keys` fields;
- run automatic orphan linking;
- enable PageRank or centrality ranking;
- change `memory_search`, bootstrap, retrieval ranking, candidate sets, tool
  routing, MCP profiles, runtime flags, daemon processes, or repository code
  paths;
- change forum thread status.

## Next Step

Stop after this packet unless graph hygiene remains the priority.

If continuing, run another read-only review packet first and keep the next
write no larger than ten exact-scope, explicit `related_keys` edges. The next
review packet currently projects only two additional orphan reductions, so the
value of another immediate write is lower than this first packet.
