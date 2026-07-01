# GHP-1d Residual Orphan Manual Review Packet

Date: 2026-07-01

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: docs-only manual review packet / no graph write

## Summary

The three strict exact durable residuals from the post-reconnect GHP-1d readout
do not justify another automatic `related_keys` materialization pass.

Recommended action: keep all three out of the automatic write queue. Treat them
as historical or cross-scope curation cases unless a future owner explicitly
opens a manual memory-curation packet.

This packet does not write `memory_edges`, edit `related_keys`, delete/archive
memories, change retrieval ranking, or change runtime behavior.

## Inputs

- Previous readout:
  `docs/reports/goal-c-u/2026-07-01-ghp1d-post-reconnect-residual-orphan-readout.md`
- Repository state at review start:
  `1fd7158 docs(memory): record ghp1d post-reconnect orphan readout`
- SQLite state DB:
  `/home/pallasting/.local/share/agent-bridge/state.db`
- Read-only `PRAGMA quick_check`: `ok`

Current read-only counts:

| Metric | Value |
|---|---:|
| `memories` | 1123 |
| `memory_edges` | 2068 |
| `edge_type='relates'` | 161 |

## Review Table

| Key | Current read | Recommendation | Reason |
|---|---|---|---|
| `verification_lcc_v1_clean_branch_voice_adapter_20260603` | Exact-scope historical decision, no `related_keys`, no graph edges. | Keep isolated. Do not invent an edge. | Search only found broad voice/deploy context plus this exact row; no specific exact-scope target is authoritative enough for an automatic link. If this lane is revived, create a fresh curated memory or explicit owner-reviewed relation then. |
| `lesson_shared_master_fast_deploy_discipline_20260529` | Exact-scope lesson with declared `related_keys` to parent-scope `session_handoff_dials_dogfood_slice2_20260529b` and `global_tells_baseline_skill_20260529`; no current graph edge. | Keep as cross-scope curation case. Do not exact-scope materialize. | The row is intentionally tied to parent-scope/global operational discipline. Linking it to a newer exact-scope deploy report would reduce an orphan counter but weaken provenance. |
| `lesson_mcp_schema_missing_type_double_encode_20260529` | Exact-scope lesson with declared parent-scope target `session_handoff_dials_dogfood_slice2_20260529b`; also has one existing `relates` edge to parent-scope `lesson_live_falsifier_proof_extract_consts_browser_eval_20260529`. | Keep as cross-scope curation case. Do not exact-scope materialize. | It is not globally edge-free; it is isolated only in the exact-scope induced graph because the existing edge points to `project:/Data/CascadeProjects`. This is a scope-policy question, not an orphan-write backlog. |

## Scope Note

The residual count is an exact-scope induced-graph measure. That matters for
`lesson_mcp_schema_missing_type_double_encode_20260529`: the live store already
contains this edge:

```text
lesson_mcp_schema_missing_type_double_encode_20260529
  --relates-->
lesson_live_falsifier_proof_extract_consts_browser_eval_20260529
```

The target is active, but its scope is `project:/Data/CascadeProjects`, so it
does not reduce the exact Agent-Bridge project residual count.

## Decision

Close GHP-1d residual orphan work as a docs-only review outcome for now.

Do not use `memory_related_keys_materialize` for these three rows unless a
future packet supplies one of the following:

1. an owner-reviewed exact-scope target and rationale for a curated edge;
2. a cross-scope materialization policy covering parent-scope targets; or
3. a supersede/archive decision for a specific historical memory row.

The new hash gate remains the correct safety contract for any future reviewed
materializer write, but this packet selects no edges for that path.

## Boundary

This packet did not:

- call `memory_related_keys_materialize`;
- write, delete, archive, or supersede memory rows;
- edit any `related_keys` field;
- mutate `memory_edges`;
- change retrieval ranking, coactivation, PageRank/centrality, tool routing,
  MCP profiles, prompts, daemons, or runtime flags;
- change forum thread status.
