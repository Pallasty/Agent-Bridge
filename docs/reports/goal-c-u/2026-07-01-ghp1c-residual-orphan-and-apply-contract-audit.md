# GHP-1c Residual Orphan and Apply-Contract Audit

Date: 2026-07-01

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: read-only audit complete

## Summary

After three small GHP-1c exact-scope `related_keys` materialization batches,
the graph-hygiene value of another broad exact-scope write is now low.

Current recommendation:

1. Stop broad exact-scope `related_keys` materialization for edge count.
2. Treat the remaining exact-scope orphan surface as a review/curation issue,
   not as an automatic-write backlog.
3. If the materializer is used again, first add a stricter apply contract:
   either an expected selected-edge hash or an explicit reviewed-edge allowlist
   so dry-run and live apply cannot drift.

## Source State

- Repository HEAD: `2134986 docs(memory): clarify related keys tiny materialization context`
- Worktree before this report: clean
- `git diff --check`: clean
- SQLite state DB: `/home/pallasting/.local/share/agent-bridge/state.db`
- Read-only `PRAGMA quick_check`: `ok`

Current edge counts from read-only SQL:

| Metric | Count |
|---|---:|
| `memory_edges` total | 2057 |
| `edge_type='relates'` | 161 |

The total edge count is higher than the last tiny-write report because durable
memory/work-memory saves created later `evolved` edges. The GHP-1c
materialization count is unchanged at 20 `relates` edges across three batches.

## GHP-1c Write Batches Observed

| Commit | Report | Edge count | `created_at` | Notes |
|---|---|---:|---:|---|
| `8e7824d` | `2026-07-01-ghp1c-related-keys-materialization.md` | 10 | 1782936089 | First exact-scope tiny write |
| `fff3b7e` | `2026-07-01-ghp1c-related-keys-supplemental-materialization.md` | 5 | 1782936155 | Supplemental exact-scope write |
| `1ff6d3d` / clarified by `2134986` | `2026-07-01-related-keys-materialization-tiny-write.md` | 5 | 1782936253 | Third exact-scope micro-batch |

No memory rows were deleted, no `related_keys` fields were edited, no automatic
orphan linking was enabled, and no PageRank/centrality/ranking/candidate-set
runtime change was made as part of these batches.

## Current Topology Readout

`memory_graph_topology` with local scope and strict durable filters:

- `non_skill_active_total=329`
- `orphan_count=7`
- `orphan_fraction=0.021`
- `p4_evolved_coverage=279`
- `p4_evolved_fraction=0.848`
- `top_hub_degree=35`
- `top_hub_fraction=0.106`
- `pagerank_readiness=observe_then_bound_centrality_boost`

This remains only a readout. It does not approve or enable a centrality prior.

## Orphan Surfaces

Different tools use different denominator/filter choices, so the current orphan
surface should be read by profile:

| Profile | Visible nodes | Orphans | Meaning |
|---|---:|---:|---|
| Strict local-compatible durable graph | 329 | 7 | Includes compatible parent-scope project memories |
| Strict exact-scope durable graph | 309 | 3 | Best read for exact project-only residual durable orphans |
| Review-packet default exact graph | 334 | 5 | Includes `session_handoff`; matches the review tool's default filters |

Strict exact-scope residual orphans:

| Key | Kind | Importance | `related_keys` shape | Read |
|---|---|---:|---|---|
| `verification_lcc_v1_clean_branch_voice_adapter_20260603` | `decision` | 0.587 | none | Voice-adapter historical verification; needs manual reviewed link or can remain historical |
| `lesson_shared_master_fast_deploy_discipline_20260529` | `lesson` | 0.166 | points to parent-scope `session_handoff_dials_dogfood_slice2_20260529b` and `global_tells_baseline_skill_20260529` | Not reducible by exact-scope materialization without cross-scope policy or different filters |
| `lesson_mcp_schema_missing_type_double_encode_20260529` | `lesson` | 0.096 | points to parent-scope `session_handoff_dials_dogfood_slice2_20260529b` | Not reducible by exact-scope materialization without cross-scope policy or different filters |

Review-packet default adds two `session_handoff` orphans:

- `biocortex_semantic_diverse_live_candidate_corpus_20260614`
- `handoff_agent_bridge_t9a_desktop_snapshot_mcp_20260529`

These explain why the review packet reports five exact-scope orphans while the
strict durable exact graph reports three.

## Candidate Edge Readout

`memory_related_keys_preflight` with local-compatible strict filters:

- `candidate_pairs=273`
- `current_edge_pairs=941`
- `current_orphans=7`
- `orphan_candidate_nodes=5`
- `orphans_reduced=5`
- `projected_orphans_after_candidates=2`

This broad preflight still sees many safe candidates, but the sample includes
parent-scope-compatible work. It should not be treated as an exact live-write
packet.

`memory_related_keys_review_packet` with exact scope and orphan-reduction
selection:

- `current_edge_pairs=1060`
- `current_orphans=5`
- `safe_candidate_pairs_before_caps=293`
- `selected_edges_count=10`
- `orphan_candidate_nodes_selected=1`
- `orphans_reduced_by_selected=1`
- `projected_orphans_after_selected=4`

The next reviewed exact packet would mostly add density. Its direct orphan
reduction is one node under the review tool's default filters, and zero or
minimal under stricter durable-only interpretation.

## Apply-Contract Risk

The third tiny-write report notes that live apply recomputed the plan at
execution time, so the authoritative written set was the live response plus SQL
verification, not the earlier dry-run sample.

That is acceptable for the completed small batch because it was backed up,
capped, verified, and reversible. It is not a good long-term contract for larger
or repeated graph writes.

Preferred next contract before any future materialization:

- dry-run returns a stable `selected_edge_hash` over normalized selected edges;
- apply accepts `expected_selected_edge_hash` and aborts if recomputation differs;
- or apply accepts an explicit reviewed `edges` allowlist and writes only those;
- post-write response includes the hash, written edges, skipped edges, and count
  deltas;
- tests cover hash mismatch, missing edge target, duplicate existing edge, and
  successful capped apply.

## Decision

GHP-1c graph hygiene should close here for broad writes. The remaining orphan
surface is small and explainable:

- exact durable residual: three historical/manual-review items;
- review default residual: five items, two of which are `session_handoff`;
- local-compatible residual: seven items, mostly because parent-scope memories
  remain in the denominator.

The next graph-hygiene work, if prioritized, should be GHP-1d apply-contract
hardening, not another edge batch.
