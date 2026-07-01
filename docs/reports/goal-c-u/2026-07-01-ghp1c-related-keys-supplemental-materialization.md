# GHP-1c Related Keys Supplemental Materialization

Date: 2026-07-01

Status: `SUPPLEMENTAL_TINY_WRITE_APPLIED / BACKED_UP / POSTCHECKED`

## Decision

Apply a supplemental five-edge exact-scope `related_keys` materialization after
the first GHP-1c ten-edge packet.

This supplement records only the second batch:

- prior report/commit: `8e7824d docs(memory): record ghp1c related-keys materialization`
- prior batch: 10 `relates` edges at `created_at=1782936089`
- this supplemental batch: 5 `relates` edges at `created_at=1782936155`

The supplemental batch used the same guarded writer,
`memory_related_keys_materialize`, through a one-shot
`AGENT_BRIDGE_TOOL_PROFILE=all` MCP subprocess. The compact Codex profile
remained unchanged.

This supplement does not approve PageRank, centrality ranking, automatic
orphan linking, or any retrieval-order change.

## Backup And Pre-Write Gate

The backup for this supplemental batch was taken after the first ten-edge
packet and before the five-edge supplemental write.

```text
source=/home/pallasting/.local/share/agent-bridge/state.db
backup=/home/pallasting/.local/share/agent-bridge/backups/state.before-ghp1c-related-keys-materialize.20260701T200141Z.db
size=192262144
sha256=a04d99b43dc17e685ff68a76373bd2375de22e7fc486509392fdcc793f3d6fd6
PRAGMA quick_check_before=ok
```

The first batch timestamp was:

```text
1782936089 = 2026-07-01T20:01:29Z
```

This supplement's backup timestamp was:

```text
2026-07-01T20:01:41Z
```

The supplemental write timestamp was:

```text
1782936155 = 2026-07-01T20:02:35Z
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
max_edges=5
max_records=2000
edge_type=relates
weight=1.0
dedupe_undirected_pairs=true
require_scope_compatible=true
max_inbound_per_target=3
max_outbound_per_source=3
skip_kinds=[alert, work_memory, session_handoff, snapshot, feedback, skill, present_outcome]
skip_tags=[auto_curated, implicit, unverified_identifier, alert, ttl:7d,
ttl:14d, ttl:30d, ttl:45d]
```

Dry-run immediately before the supplemental write:

```text
blocked=false
selected_edges=5
linked=0
selected_edge_hash_v1=4759226f9bad06d0952541bf60ae81e60adcbde7efeeabd757123aeb68f9f231
```

Live write result:

```text
blocked=false
linked=5
write_errors=[]
selected_edges=5
selected_edge_hash_v1=4759226f9bad06d0952541bf60ae81e60adcbde7efeeabd757123aeb68f9f231
```

## Materialized Edges

| From | To |
|---|---|
| `decision_ab_parent_dir_w3_impl_verified_closed_20260630` | `decision_ab_parent_dir_w2_pagination_done_20260630` |
| `decision_ab_parent_dir_w3_impl_verified_closed_20260630` | `decision_ab_parent_dir_w2_scripts_macos_fallbacks_20260630` |
| `arc3_substrate_snapshot_schema_contract_shipped_20260630` | `lesson_seed_bridge_unbuildable_isolate_snapshot_verify_20260630` |
| `biocortex_retrieval_shadow_live_verified_20260610` | `biocortex_retrieval_shadow_codex_exposed_20260610` |
| `biocortex_retrieval_shadow_live_verified_20260610` | `biocortex_retrieval_shadow_installed_20260610` |

Each selected row was read back from `memory_edges` with:

```text
edge_type=relates
weight=1.0
created_at=1782936155
```

## Post-Write Checks

SQLite:

```text
PRAGMA quick_check_after=ok
verified_requested_edges=5
memory_edges_total=2041
```

Exact topology with the durable-project filters from the P1 audit:

| Metric | Before P1 audit | After 10-edge packet | After supplemental 5 |
|---|---:|---:|---:|
| non-skill active total | 355 | 357 | 357 |
| orphan count | 17 | 14 | 13 |
| orphan fraction | 0.048 | 0.039 | 0.036 |
| P4 evolved coverage | 300 | 302 | 302 |
| P4 evolved fraction | 0.845 | 0.846 | 0.846 |
| top hub degree | 37 | 37 | 37 |
| top hub fraction | 0.104 | 0.104 | 0.104 |

`memory_related_keys_preflight` after the supplemental batch:

| Metric | Value |
|---|---:|
| current edge pairs | 1090 |
| safe candidate pairs | 329 |
| current orphans | 13 |
| orphan candidate nodes | 10 |
| projected orphans after candidates | 3 |

`memory_related_keys_review_packet` with exact-scope orphan-reduction selection
after the supplemental batch:

| Metric | Value |
|---|---:|
| current edge pairs | 1050 |
| current orphans | 5 |
| selected edges for next packet | 10 |
| orphans reduced by next selected | 1 |
| projected orphans after next selected | 4 |

Read: the supplemental batch produced one additional durable-topology orphan
reduction after the first ten-edge packet. The next review packet now projects
only one more orphan reduction under its default filters, so stop here unless
graph hygiene remains the explicit priority.

## Rollback

Primary rollback for this supplement can delete exactly the five inserted
edges:

```sql
DELETE FROM memory_edges
WHERE edge_type='relates'
  AND created_at=1782936155
  AND (from_key, to_key) IN (
    ('decision_ab_parent_dir_w3_impl_verified_closed_20260630','decision_ab_parent_dir_w2_pagination_done_20260630'),
    ('decision_ab_parent_dir_w3_impl_verified_closed_20260630','decision_ab_parent_dir_w2_scripts_macos_fallbacks_20260630'),
    ('arc3_substrate_snapshot_schema_contract_shipped_20260630','lesson_seed_bridge_unbuildable_isolate_snapshot_verify_20260630'),
    ('biocortex_retrieval_shadow_live_verified_20260610','biocortex_retrieval_shadow_codex_exposed_20260610'),
    ('biocortex_retrieval_shadow_live_verified_20260610','biocortex_retrieval_shadow_installed_20260610')
  );
```

Full rollback for this supplement can restore the SQLite backup listed above;
that backup already includes the earlier ten-edge packet and excludes only this
supplemental five-edge batch.

## Boundary

This supplement did not:

- write or delete durable memory rows;
- modify `related_keys` fields;
- run automatic orphan linking;
- enable PageRank or centrality ranking;
- change `memory_search`, bootstrap, retrieval ranking, candidate sets, tool
  routing, MCP profiles, runtime flags, daemon processes, or repository code
  paths;
- change forum thread status.
