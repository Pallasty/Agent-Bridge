# GHP-1c Tiny `related_keys` Materialization Write

Date: 2026-07-01

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: completed, small reversible write

## Summary

Executed a guarded 5-edge `related_keys` materialization batch through the
existing `memory_related_keys_materialize` MCP tool.

The tool is intentionally not exposed in the current `codex-essential` surface.
It is implemented and tested in the repo, and is reachable from a temporary
`AGENT_BRIDGE_TOOLSET=all-dev` MCP subprocess. No direct SQLite mutation was
used for the write.

## Guardrails

- Write path: `memory_related_keys_materialize`
- Tool policy: temporary local `AGENT_BRIDGE_TOOLSET=all-dev`
- Confirmation: `apply_confirmation="materialize_related_keys"`
- `dry_run=false` only after a successful dry-run
- `scope_filter=exact`
- `scope_mode=local_only`
- `selection_strategy=orphan_reduction`
- `max_edges=5`
- `max_outbound_per_source=3`
- `max_inbound_per_target=3`
- `edge_type=relates`
- `weight=1.0`

The write stayed out of raw orphan-linking and did not change retrieval ranking.

## Backup

SQLite CLI was not installed on the host, so integrity checks used Python's
standard `sqlite3` module.

- Pre-write `PRAGMA quick_check`: `ok`
- Backup path:
  `/home/pallasting/.local/share/agent-bridge/backups/state.before-related-keys-materialize.20260701T130334-0700.db`
- Backup method: SQLite backup API from read-only source connection
- Backup sha256:
  `5bbd89c7bae629db12b3178491fdf6b119553cc87657b00865f258c5e5120a0e`

## Pre-Write Dry-Run

Arguments:

```json
{
  "dry_run": true,
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "scope_mode": "local_only",
  "scope_filter": "exact",
  "selection_strategy": "orphan_reduction",
  "max_records": 1500,
  "max_edges": 5,
  "max_outbound_per_source": 3,
  "max_inbound_per_target": 3,
  "preview_chars": 120
}
```

Result:

- `selected_edges_count=5`
- `linked=0`
- `write_errors=[]`
- `current_edge_pairs=894`
- `current_orphans=3`
- `safe_candidate_pairs_before_caps=264`
- `orphans_reduced_by_selected=0`
- `projected_orphans_after_selected=3`

Read: exact-scope materialization still has explicit-link backlog, but the next
exact-scope tiny batch is graph-density work, not orphan-reduction work.

## Live Write

The live call recomputed the plan at execution time. The authoritative written
set is therefore the live response plus SQL verification below, not the earlier
dry-run sample.

Live result:

- `blocked=false`
- `linked=5`
- `write_errors=[]`
- `selected_edges_count=5`
- `current_edge_pairs=899`
- `current_orphans=3`
- `safe_candidate_pairs_before_caps=266`
- `orphans_reduced_by_selected=0`
- `projected_orphans_after_selected=3`

Written edges:

| from_key | to_key |
|---|---|
| `biocortex_opt_in_review_packet_20260611` | `biocortex_opt_in_audit_shape_20260611` |
| `ghp1_related_keys_review_packet_20260622` | `controlled_rsi_goal_c_local_run_and_closure_20260621` |
| `ghp1b_tiny_write_review_packet_20260622` | `ghp1b_orphan_reduction_selection_deployed_20260622` |
| `trigger_recall_pre_policy_hold_post_install_mcp_stale_check_20260623` | `trigger_recall_pre_policy_hold_aio2_audit_evidence_20260623` |
| `agent_bridge_scope_canonical_host_policy_packet_20260625` | `agent_bridge_memory_authorization_contracts_20260625` |

All five rows were present post-write as `edge_type='relates'`, `weight=1.0`,
`created_at=1782936253`.

## SQL Verification

Read-only SQL count check:

| DB | `memory_edges` | `relates` |
|---|---:|---:|
| backup | 2046 | 156 |
| live | 2051 | 161 |

Post-write `PRAGMA quick_check`: `ok`

## Post-Write Topology

`memory_graph_topology` with local scope and the same volatile filters:

- `non_skill_active_total=330`
- `orphan_count=7`
- `orphan_fraction=0.021`
- `p4_evolved_coverage=280`
- `p4_evolved_fraction=0.848`
- `top_hub_degree=35`
- `top_hub_fraction=0.106`
- `pagerank_readiness=observe_then_bound_centrality_boost`

The PageRank readiness label is only a readout. This packet did not enable a
centrality prior.

## Post-Write Preflight

`memory_related_keys_preflight`, local scope:

- `candidate_pairs=275`
- `current_edge_pairs=942`
- `current_orphans=7`
- `orphan_candidate_nodes=5`
- `orphans_reduced=5`
- `projected_orphans_after_candidates=2`
- `visible_total=330`

This preflight is broader than the exact materializer packet because it does not
carry `scope_filter=exact`; its sample included parent-scope rows. Do not use
the raw preflight sample as a live-write packet.

Post-write exact materializer dry-run:

- `current_edge_pairs=904`
- `current_orphans=3`
- `safe_candidate_pairs_before_caps=261`
- `selected_edges_count=5`
- `orphans_reduced_by_selected=0`
- `projected_orphans_after_selected=3`

Read: another exact-scope tiny write is still possible, but its immediate value
is low unless the goal is explicit-link density rather than orphan reduction.

## Rollback

Preferred full rollback:

1. Stop agent-bridge writers.
2. Restore the backup DB listed above.
3. Re-run `PRAGMA quick_check`.
4. Re-run graph topology and related-keys preflight.

Narrow rollback, if full restore is too broad:

```sql
DELETE FROM memory_edges
WHERE edge_type = 'relates'
  AND weight = 1.0
  AND created_at = 1782936253
  AND (
    (from_key = 'biocortex_opt_in_review_packet_20260611'
     AND to_key = 'biocortex_opt_in_audit_shape_20260611')
    OR (from_key = 'ghp1_related_keys_review_packet_20260622'
        AND to_key = 'controlled_rsi_goal_c_local_run_and_closure_20260621')
    OR (from_key = 'ghp1b_tiny_write_review_packet_20260622'
        AND to_key = 'ghp1b_orphan_reduction_selection_deployed_20260622')
    OR (from_key = 'trigger_recall_pre_policy_hold_post_install_mcp_stale_check_20260623'
        AND to_key = 'trigger_recall_pre_policy_hold_aio2_audit_evidence_20260623')
    OR (from_key = 'agent_bridge_scope_canonical_host_policy_packet_20260625'
        AND to_key = 'agent_bridge_memory_authorization_contracts_20260625')
  );
```

Use narrow rollback only with a fresh backup and quick_check.

## Follow-Up

Do not continue broad exact-scope materialization just to increase edge count.
The next higher-value graph hygiene step is either:

1. investigate the remaining exact-scope 3-orphan surface, or
2. design a stricter live materializer apply contract with `plan_hash` or an
   explicit reviewed-edge allowlist so `dry_run` and `apply` cannot drift.

