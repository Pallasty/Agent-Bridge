# Goal C U Follow-Up - GHP-1 Related Keys Review Packet

Date: 2026-06-22

Host: Linux/Aio2

Scope: read-only GHP-1 review packet after deploy/reconnect to current
`origin/master`.

Verdict: `actionable` for report review and selection tuning only.

This run did not write graph edges, mutate memory rows, change retrieval
ranking, approve PageRank or centrality as a live ranking prior, add an MCP
surface, approve runtime candidate expansion, or authorize an executor.

## Source Anchors

| Anchor | Value |
|---|---|
| source commit | `d9eb8ca03b158e53f3b5eeaa2e449c2dda1166d0` |
| source subject | `feat(eval): add offline para-ml anisotropy + hash-noise recall probe` |
| deployed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| deployed sha256 | `c28d14a01f0fa41b5836bc1f6aafbb5c506d1f633b6a9438f64c56da806fdce0` |
| deployed version | `ab-bridge 0.1.0` |
| report target | `docs/reports/goal-c-u/2026-06-22-ghp1-related-keys-review-packet.md` |

## Runtime And Board State

After deploy and Codex MCP reconnect:

- `agent-bridge.real doctor`: `8 ok / 0 warn / 0 fail`;
- two MCP servers were present and both executed the current `.real` binary;
- `mcp_lifecycle_digest`: lifecycle `ready`, readiness `ready`, runtime health
  `ready`;
- daemon-http `/healthz`: `ok`;
- Palace `/healthz`: `ok`;
- Palace `/api/graph`: observed;
- Palace `/api/semantic-events`: observed.

Forum digest showed no fresh local blocker:

- #105 remains the local Goal C mirror thread.
- #102 remains the AB borrowed-patterns landing kanban.
- #104 remains stale BioCortex runtime-influence review context.
- Thread #120 remains referenced by remote Goal C docs but is not readable in
  this local forum store.

## Review Packet Run

Tool:

`memory_related_keys_review_packet`

Parameters:

| Parameter | Value |
|---|---|
| `scope` | `project:/Data/CascadeProjects/agent-bridge` |
| `scope_mode` | `local_only` |
| `scope_filter` | `exact` |
| `max_pairs` | `20` |
| `max_records` | `1000` |
| `preview_chars` | `180` |

Default safety filters were active:

- generated-noise rows filtered by default;
- `auto_curated`, `implicit`, `unverified_identifier`, `alert`, `ttl:7d`,
  and `ttl:14d` skipped;
- `alert`, `work_memory`, and `snapshot` kinds skipped;
- no raw source packet included;
- no writes authorized.

### Packet Summary

| Metric | Value |
|---|---:|
| loaded records | 436 |
| visible total | 138 |
| current edge pairs | 283 |
| current orphans | 35 |
| safe candidate pairs before caps | 99 |
| selected edges | 20 |
| selected orphan candidate nodes | 1 |
| projected orphans reduced by selected edges | 1 |
| projected orphans after selected edges | 34 |

Bucket counts:

| Bucket | Pairs | Sources |
|---|---:|---:|
| already_has_edge | 76 | 46 |
| selected | 20 | 15 |
| skipped_max_edges | 78 | 53 |
| target_missing | 22 | 18 |
| target_scope_filtered | 7 | 5 |
| target_scope_not_exact | 4 | 3 |
| duplicate_candidate | 1 | 1 |
| skipped_outbound_cap | 1 | 1 |

Top selected source clusters:

- LSWR runtime executor design preflight lineage.
- BioCortex retrieval shadow and opt-in authorization lineage.
- BioCortex live LSWR action-result runtime observation lineage.

Top selected targets included:

- `biocortex_runtime_boundary_proof_20260611`;
- `lswr_interaction_feedback_patch_apply_request_acceptance_20260616`;
- `biocortex_retrieval_shadow_codex_exposed_20260610`;
- `biocortex_retrieval_shadow_installed_20260610`;
- `biocortex_two_layer_approval_model_20260611`.

## Comparison: Generic Preflight

Tool:

`memory_related_keys_preflight`

Same scope and noise filters, but without exact review-packet selection.

| Metric | Value |
|---|---:|
| visible total | 155 |
| current edge pairs | 283 |
| current orphans | 52 |
| safe candidate pairs | 125 |
| candidate sources | 80 |
| candidate targets | 80 |
| orphan candidate nodes | 40 |
| projected orphans after all candidates | 12 |
| projected orphans reduced by all candidates | 40 |

Interpretation:

- The broader preflight says explicit `related_keys` have enough signal to be
  useful.
- The stricter capped review packet selected semantically coherent lineage
  edges, but only one selected edge reduced orphan pressure.
- Therefore the first capped review batch is not a good write batch as-is.

## Topology Context

Project-scoped topology with generated-noise filters:

| Metric | `local_only` | `local_plus_global` |
|---|---:|---:|
| non-skill active total | 155 | 165 |
| orphan count | 52 | 62 |
| orphan fraction | 0.335 | 0.376 |
| P4 evolved coverage | 103 | 103 |
| P4 evolved fraction | 0.665 | 0.624 |
| top hub degree | 24 | 24 |
| top hub fraction | 0.155 | 0.145 |
| PageRank readiness | `hub_risk_cap_centrality_boost` | `needs_graph_hygiene_before_rank_prior` |

Top hubs remained BioCortex-heavy:

- `biocortex_opt_in_runtime_trial_20260611`;
- `biocortex_opt_in_review_packet_20260611`;
- `biocortex_retrieval_verification_bundle_20260610`.

The local graph is better than the broad graph, but hub risk remains visible.
This still argues against live centrality or PageRank influence.

## Replayability

`event_spine_snapshot(window_secs=86400, limit=200)` reported:

- chain verified: `true`;
- event count: `200`;
- truncated count: `12`;
- source rows: `188` MCP tool calls and `12` MCP tool errors;
- chain head:
  `c6300a758ef0724f98a41927e6d84e69323fb5265d3f8af97b48cb3182089cab`.

## Decision

GHP-1 should continue, but only as review/report work for now.

The current selected packet is useful evidence that the tool is filtering and
staying within the intended safety boundary. It is not yet a strong write
candidate because the capped selected batch would reduce only one orphan.

Next safe action:

1. Review whether the selected BioCortex/LSWR lineage edges have semantic value
   independent of orphan reduction.
2. Prepare or run a follow-up review packet that prioritizes orphan-reducing
   explicit `related_keys` while keeping exact scope, generated-noise filters,
   and a 20-pair cap.
3. Only after a reviewed batch is worth writing, use the separate guarded writer
   path with SQLite backup, `PRAGMA quick_check`, a tiny batch, and a topology
   rerun.

## Non-Authorizations

This report does not authorize:

- `memory_related_keys_materialize` in write mode;
- graph edge writes;
- automatic orphan linking;
- PageRank, centrality, or graph-neighbor live ranking;
- memory row rewrites;
- retrieval-order changes;
- new MCP tools;
- approval-gated executors.

## Rollback

This report changes only documentation. To revert it:

```bash
git revert <commit-that-adds-this-report>
```

No runtime restart is required for the document itself.
