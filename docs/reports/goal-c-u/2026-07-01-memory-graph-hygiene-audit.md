# Memory Graph Hygiene Audit

Date: 2026-07-01

Status: `READ_ONLY_AUDIT / NO_EDGE_WRITE / NO_RANKING_CHANGE`

## Decision

Do not mutate memory graph edges or retrieval ranking in this pass.

The exact Agent-Bridge graph is healthy enough for targeted hygiene, but the
lowest-risk next action is a separate guarded `related_keys` materialization
packet, not automatic orphan linking and not a PageRank/centrality ranking
change.

## Scope

Project:

```text
project:/Data/CascadeProjects/agent-bridge
```

Repo head at audit:

```text
e7a4657 docs(memory): record board hygiene first status pass
```

Worktree:

```text
## master...origin/master
```

Common filters used for the exact-scope graph checks:

```text
scope=project:/Data/CascadeProjects/agent-bridge
scope_mode=local_only
skip_kinds=[work_memory]
skip_tags=[ttl:7d, ttl:14d, ttl:30d, ttl:45d]
```

These filters intentionally keep durable project memories while excluding
short-lived scratchpad rows.

Companion broader-surface report:

```text
docs/reports/goal-c-u/2026-07-01-memory-graph-hygiene-readonly-audit.md
```

That report uses a different `local_plus_global` posture and surfaces generated
or implicit row noise. Treat its counts as a broader safety check, not a
replacement for the exact-scope counts below.

## Inputs

Read-only MCP tools used:

- `memory_graph_topology`, exact scope;
- `memory_graph_topology`, local plus global;
- `memory_orphan_inventory`;
- `memory_orphan_candidates`;
- `memory_related_keys_preflight`;
- `memory_related_keys_review_packet`;
- `memory_consolidation_queue`.

No write-capable memory tool was called.

## Topology

Exact Agent-Bridge scope:

| Metric | Value |
|---|---:|
| active non-skill memories | 355 |
| orphan count | 17 |
| orphan fraction | 0.048 |
| P4 evolved coverage | 300 |
| P4 evolved fraction | 0.845 |
| top hub degree | 37 |
| top hub fraction | 0.104 |
| readiness label | `observe_then_bound_centrality_boost` |

Degree histogram:

| Degree bucket | Count |
|---|---:|
| 0 | 17 |
| 1 | 37 |
| 2-3 | 75 |
| 4-5 | 76 |
| 6-10 | 93 |
| 11-20 | 44 |
| 21+ | 13 |

Local plus global view:

| Metric | Value |
|---|---:|
| active non-skill memories | 419 |
| orphan count | 46 |
| orphan fraction | 0.110 |
| P4 evolved coverage | 332 |
| P4 evolved fraction | 0.792 |
| top hub degree | 39 |
| top hub fraction | 0.093 |

Interpretation: exact Agent-Bridge scope is materially cleaner than the
local-plus-global view. Future hygiene should keep exact-scope and cross-scope
work separated, as with the recent `work_memory` cleanup sequence.

## Orphan Inventory

Eligible exact-scope orphan rows:

| Kind | Count |
|---|---:|
| `decision` | 6 |
| `session_handoff` | 6 |
| `lesson` | 2 |
| `context` | 1 |
| `fact` | 1 |
| `reference` | 1 |

High-signal examples:

| Key | Kind | Current read |
|---|---|---|
| `agent_bridge_scope_phase3_aio2_dryrun_20260625` | decision | high-importance scope/canonical-host blocker context with one related key but no graph edge |
| `decision_borrow_landing_outcomes_20260628` | decision | borrowed-patterns outcome summary with multiple related keys |
| `biocortex_semantic_diverse_live_candidate_corpus_20260614` | session_handoff | BioCortex live-candidate corpus handoff with obvious same-scope BioCortex neighbors |
| `handoff_agent_bridge_t9a_desktop_snapshot_mcp_20260529` | session_handoff | desktop snapshot MCP handoff with a clear T9b vision-grounding neighbor |
| `lesson_seed_bridge_unbuildable_isolate_snapshot_verify_20260630` | lesson | useful build-boundary lesson, currently isolated |

The inventory also surfaces several parent-scope output/present voice rows.
Those should not be blended into an exact Agent-Bridge write without explicit
scope compatibility review.

## Orphan Candidate Preview

`memory_orphan_candidates` examined 362 records and returned:

```text
eligible_orphans=11
would_link=10
low_score=1
threshold=0.72
```

Strong examples:

| Orphan | Top candidate shape |
|---|---|
| `biocortex_semantic_diverse_live_candidate_corpus_20260614` | same-scope BioCortex runtime/approval packet decisions, confidence 1.0 |
| `handoff_agent_bridge_t9a_desktop_snapshot_mcp_20260529` | `handoff_agent_bridge_t9b_vision_grounding_mcp_20260529`, confidence 1.0 |
| `agent_bridge_northstar_bidirectional_bridge_20260529` | north-star/taste-skill/presentation context cluster, confidence 1.0 |
| `session_handoff_e2_interactive_present_deploy_pending_20260529` | present_voice / taste-skill / dials handoff cluster, confidence 1.0 |

One low-score item was the filesystem migration fact
`fact_cascadeprojects_migrated_to_data_symlink_20260610`; do not force-link it
by lowering thresholds.

## Related Keys Preflight

Explicit `related_keys` materialization is the highest-leverage hygiene path.

`memory_related_keys_preflight` reported:

| Metric | Value |
|---|---:|
| current edge pairs | 1067 |
| current orphans | 17 |
| safe candidate pairs | 340 |
| candidate sources | 203 |
| candidate targets | 191 |
| orphan candidate nodes | 14 |
| projected orphans after candidates | 3 |

Important buckets:

| Bucket | Pairs |
|---|---:|
| already_has_edge | 283 |
| safe_candidate | 340 |
| target_missing | 66 |
| target_scope_filtered | 40 |
| duplicate_candidate | 13 |

`memory_related_keys_review_packet` selected a capped 30-edge review packet:

```text
ready=true
block_reasons=[]
selected_edges=30
orphans_reduced_by_selected=14
projected_orphans_after_selected=3
```

This is review evidence only. It grants no write authority by itself.

## Consolidation Queue

`memory_consolidation_queue` reported:

| Bucket | Count |
|---|---:|
| handoff_to_decision | 12 |
| high_token_low_use | 1 |
| duplicate_lessons | 0 |
| harmful_memories | 0 |
| stale_warnings | 0 |
| too_large_memories | 0 |
| intentional_orphans | 0 |

Interpretation: the graph issue is not primarily toxic/duplicate memory. The
main opportunity is making already-declared relationships explicit and later
promoting selected high-value handoffs into concise durable decisions or
lessons.

## Recommendations

1. Do not enable PageRank or centrality ranking from this audit alone.

   Exact-scope topology is acceptable, but graph improvements should first
   reduce orphan ambiguity and materialize explicit relationships. Ranking
   changes need a separate shadow/eval packet.

2. Use `related_keys` materialization as the next graph-hygiene implementation
   packet if continuing this lane.

   Required write packet contract:

   - create a SQLite backup first;
   - use a small reviewed batch, starting with the 30 selected edges or a
     stricter subset;
   - prefer exact Agent-Bridge project-scope pairs before global or
     parent-scope pairs;
   - exclude generated/noisy rows such as `auto_curated`, `implicit`,
     `unverified_identifier`, snapshots, alerts, `work_memory`, feedback,
     skills, and `present_outcome`;
   - run `PRAGMA quick_check` or the project equivalent before and after;
   - write only `relates` edges derived from explicit `related_keys`;
   - rerun `memory_graph_topology`, `memory_orphan_inventory`, and
     `memory_related_keys_preflight` after the write;
   - post rollback instructions and the backup hash.

3. Do not lower orphan candidate thresholds just to reduce orphan count.

   The symlink migration fact is a clear example where low-score linking would
   add noise. Precision matters more than reaching zero orphan rows.

4. Defer handoff consolidation to a later docs/memory pass.

   The 12 `handoff_to_decision` rows are high-value but broader in blast radius
   than edge materialization. They should be summarized only with explicit
   supersession or preservation boundaries.

## Boundary

This audit did not:

- write memory graph edges;
- delete, archive, or supersede memory rows;
- call a write-capable orphan-linking tool;
- change retrieval ranking, PageRank, centrality, bootstrap, tool routing, or
  MCP profiles;
- change forum thread status;
- restart daemons, change runtime flags, or deploy binaries.

## Next Step

If continuing memory graph hygiene, prepare a guarded `related_keys`
materialization packet. Otherwise stop here: the queue/board cleanup sequence is
complete and the next implementation lane should be chosen from a fresh owner
ask.
