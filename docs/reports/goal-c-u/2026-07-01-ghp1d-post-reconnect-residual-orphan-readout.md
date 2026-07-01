# GHP-1d Post-Reconnect Residual Orphan Readout

Date: 2026-07-01

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: read-only verification complete

## Summary

After the GHP-1d `memory_related_keys_materialize` apply-hash gate deployment
and MCP reconnect, the runtime surface is clean and the residual orphan picture
matches the previous GHP-1c closeout audit.

No graph edges, memories, retrieval settings, or runtime ranking behavior were
changed in this pass.

## Runtime State

`agent-bridge.real doctor` after MCP reconnect:

```text
9 ok / 0 warn / 0 fail
```

The stale MCP warning from the post-deploy state is gone:

- 11 MCP server processes were reported.
- All were executing the current `agent-bridge.real`.

Repository state:

```text
master == origin/master
HEAD = 4df6ae3 docs(memory): record final hash gate deploy evidence
```

## Store Read-Only Checks

SQLite database:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Read-only integrity and counts:

| Metric | Value |
|---|---:|
| `PRAGMA quick_check` | `ok` |
| `memories` | 1123 |
| `memory_edges` | 2068 |
| `edge_type='evolved'` | 1763 |
| `edge_type='relates'` | 161 |
| `edge_type='cofires'` | 63 |
| `edge_type='supersedes'` | 60 |
| `edge_type='co_referenced'` | 14 |
| `edge_type='corrects'` | 5 |
| `edge_type='implements'` | 1 |
| `edge_type='caused_by'` | 1 |

## Residual Orphan Views

The readout used Python's standard `sqlite3` module in read-only mode because
the `sqlite3` CLI is not installed on this machine.

Strict noisy/generated exclusions:

```text
skip_kinds=[alert, work_memory, session_handoff, snapshot, feedback, skill, present_outcome]
skip_tags=[auto_curated, implicit, unverified_identifier, alert, ttl:7d,
ttl:14d, ttl:30d, ttl:45d, source:precompact]
```

### Strict Exact Durable

This is the best view for the exact project-only durable residual surface.

| Metric | Value |
|---|---:|
| eligible records | 311 |
| orphan records | 3 |

Residual rows:

| Key | Kind | Importance | Read |
|---|---|---:|---|
| `verification_lcc_v1_clean_branch_voice_adapter_20260603` | `decision` | 0.587 | Historical voice-adapter verification; no `related_keys`; not reducible by `related_keys` materialization. |
| `lesson_shared_master_fast_deploy_discipline_20260529` | `lesson` | 0.166 | Points to parent-scope `session_handoff_dials_dogfood_slice2_20260529b` and `global_tells_baseline_skill_20260529`; not exact-scope reducible under current policy. |
| `lesson_mcp_schema_missing_type_double_encode_20260529` | `lesson` | 0.096 | Points to parent-scope `session_handoff_dials_dogfood_slice2_20260529b`; not exact-scope reducible under current policy. |

### Review-Default Exact

This keeps `session_handoff` in the exact-scope denominator, matching the
review-packet style interpretation.

| Metric | Value |
|---|---:|
| eligible records | 335 |
| orphan records | 5 |

Additional rows beyond the strict durable three:

- `biocortex_semantic_diverse_live_candidate_corpus_20260614`
- `handoff_agent_bridge_t9a_desktop_snapshot_mcp_20260529`

### Strict Local-Compatible Durable

This allows parent-scope compatible project memories in the denominator.

| Metric | Value |
|---|---:|
| eligible records | 331 |
| orphan records | 7 |

This view adds parent-scope historical rows such as:

- `agent_bridge_northstar_bidirectional_bridge_20260529`
- `deploy_piper_live_aio2_plus_say_review_20260603`
- `output_lane_e1_shipped_thread92_20260529`
- `fact_cascadeprojects_migrated_to_data_symlink_20260610`
- `reference_biocortex_rs_maturity_boundary_20260529`

## Interpretation

The previous GHP-1c closeout conclusion still holds:

1. Another broad exact-scope `related_keys` write would mostly add density, not
   materially reduce the strict durable residual surface.
2. The three exact durable residuals are explainable:
   - one historical decision has no `related_keys`;
   - two lessons point to parent-scope targets and require a cross-scope policy
     decision, not another exact-scope materialization pass.
3. The GHP-1d hash gate is now the correct safety contract for any future
   reviewed materializer write.

## Recommended Next Step

Do not run another graph write as the default next action.

If graph hygiene remains the priority, choose one of these narrower tasks:

1. Create a manual review packet for the three strict exact durable residuals,
   deciding whether each should remain isolated, receive a curated exact-scope
   `related_keys` target, or be superseded/archived.
2. Separately design a cross-scope policy for parent-scope targets before
   allowing any materialization that crosses `project:/Data/CascadeProjects`
   and `project:/Data/CascadeProjects/agent-bridge`.
3. Otherwise pivot away from GHP-1c/1d and choose the next non-graph runtime or
   retrieval-evidence lane from the board.

