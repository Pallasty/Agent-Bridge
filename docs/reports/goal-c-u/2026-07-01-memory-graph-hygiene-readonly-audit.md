# Memory Graph Hygiene Read-Only Audit

Date: 2026-07-01

Status: `READ_ONLY_AUDIT / NO_GRAPH_WRITE / NO_RANKING_CHANGE`

## Decision

Do not write memory graph edges, enable PageRank-like centrality, or change
retrieval ranking from this audit.

The Agent-Bridge memory graph is healthy enough to inspect, but the current
candidate surface mixes high-quality explicit `related_keys` gaps with
generated/noisy orphan clusters. The right next step is a separate tiny,
reviewed write packet with backup and topology post-check, not automatic orphan
linking.

## Inputs

Read-only tools:

- `semantic_bus_runtime_health`
- `memory_orphan_inventory`
- `memory_orphan_candidates`
- `memory_related_keys_preflight`
- `memory_related_keys_review_packet`

Scope:

```text
project:/Data/CascadeProjects/agent-bridge
scope_mode=local_plus_global
```

Companion exact-scope report:

```text
docs/reports/goal-c-u/2026-07-01-memory-graph-hygiene-audit.md
```

This report intentionally uses a broader local-plus-global posture to expose
generated/noisy row risks. Do not compare its counters one-for-one with the
exact-scope report; use both to constrain a future write packet.

Common exclusions:

```text
work_memory
feedback
skill
present_outcome
source:precompact
```

No SQLite writes, `memory_edges` writes, durable memory edits, forum status
changes, runtime changes, or retrieval-order changes were performed by the
audit tools.

## Runtime Graph Snapshot

The local daemon-http and Palace surfaces were ready:

```text
daemon_http_health=200 ok
palace_health=200 ok
palace_graph_observed=true
palace_semantic_events_status=ok
```

Point-in-time Palace memory-region stats:

| Metric | Value |
|---|---:|
| nodes | 500 |
| edges | 1941 |
| explicit_edges | 1797 |
| coactivation_edges | 144 |
| connected_ratio | 0.890 |
| orphan_nodes | 55 |
| stale_nodes | 81 |
| hub_nodes | 25 |

These Palace counters move as the live memory region changes. Treat them as
audit-scoping signals, not acceptance gates.

## Orphan Inventory

`memory_orphan_inventory` inspected 424 records.

| Metric | Value |
|---|---:|
| orphan_total | 58 |
| eligible_orphans | 45 |
| returned_rows | 30 |

Eligible orphans by kind:

| Kind | Count |
|---|---:|
| lesson | 18 |
| session_handoff | 10 |
| decision | 8 |
| snapshot | 4 |
| alert | 1 |
| architecture | 1 |
| context | 1 |
| fact | 1 |
| reference | 1 |

Top orphan tags were dominated by generated rows:

| Tag | Count |
|---|---:|
| auto_curated | 16 |
| implicit | 16 |
| agent-bridge | 11 |
| 2026-05-29 | 6 |
| 2026-06-03 | 5 |

Read: the orphan surface is not a pure "missing useful edge" queue. A large
chunk is generated or implicit memory, so lowering thresholds just to reduce
orphan count would be unsafe.

## Orphan Candidate Preflight

`memory_orphan_candidates` inspected a capped 20-orphan sample.

| Metric | Value |
|---|---:|
| eligible_orphans_examined | 20 |
| would_link | 19 |
| skipped_low_score | 1 |
| skipped_no_candidates | 0 |
| threshold | 0.45 |

Useful high-confidence clusters:

| Orphan | Top candidate read |
|---|---|
| `agent_bridge_northstar_bidirectional_bridge_20260529` | strong same-scope relation to north-star/taste-skill bridge records |
| `biocortex_semantic_diverse_live_candidate_corpus_20260614` | strong same-scope relation to BioCortex runtime approval/boundary records |
| `session_handoff_e2_interactive_present_deploy_pending_20260529` | strong relation to output/present handoff records |

Unsafe/noisy pattern:

- many `curated_implicit_*` rows score 1.0 against each other by shared prefix
  and tag overlap;
- those are not good first-write candidates without an explicit generated-row
  policy;
- `fact_cascadeprojects_migrated_to_data_symlink_20260610` stayed below the
  threshold at top confidence 0.42 and should not be force-linked.

## Related Keys Preflight

`memory_related_keys_preflight` inspected up to 1500 records and loaded 681.

| Metric | Value |
|---|---:|
| current_edge_pairs | 1163 |
| safe_candidate_pairs | 414 |
| candidate_sources | 233 |
| candidate_targets | 218 |
| current_orphans | 47 |
| orphan_candidate_nodes | 20 |
| projected_orphans_after_candidates | 27 |
| target_missing pairs | 83 |
| target_scope_filtered pairs | 23 |

Largest kind pair:

```text
decision -> decision: 288 pairs
```

Largest compatible scope pair:

```text
project:/Data/CascadeProjects/agent-bridge -> project:/Data/CascadeProjects/agent-bridge: 307 pairs
```

Read: explicit `related_keys` contain a real backlog. The safe-candidate count
is large enough that any write path needs caps, source/target quotas, and
reviewed batches.

## Review Packet

`memory_related_keys_review_packet` used stricter defaults:

- excluded `alert`, `work_memory`, `snapshot`;
- excluded generated/noisy tags `auto_curated`, `implicit`,
  `unverified_identifier`, `alert`, `ttl:7d`, and `ttl:14d`;
- selected with `selection_strategy=orphan_reduction`.

Result:

| Metric | Value |
|---|---:|
| packet_ready | true |
| safe_candidate_pairs_before_caps | 415 |
| selected_edges | 20 |
| selected_sources | 15 |
| current_edge_pairs | 1225 |
| current_orphans | 23 |
| orphans_reduced_by_selected | 15 |
| projected_orphans_after_selected | 8 |

Selected candidates are more plausible than the raw orphan-candidate queue
because they are explicit `related_keys` edges and filter out generated noise.
Examples include:

| Source | Target | Read |
|---|---|---|
| `decision_borrow_landing_outcomes_20260628` | `decision_borrowed_patterns_cascade_scan_20260628` | good same-scope borrow-lane edge |
| `decision_borrow_landing_outcomes_20260628` | `todo_t1_side_signal_scorer_sharpen_20260628` | good same-scope follow-up edge |
| `decision_borrow_landing_outcomes_20260628` | `todo_t2_quant_draft_unverified_20260628` | good same-scope follow-up edge |
| `agent_bridge_bdca_landed_20260603` | `session_handoff_ms_wet_test_aio2_ready_20260603` | plausible global handoff edge |
| `agent_bridge_northstar_bidirectional_bridge_20260529` inbound candidates | north-star/output/taste handoff records | plausible, but broader than exact repo scope |

## Recommendation

Proceed only with a separate `GHP-1c tiny related_keys materialization packet`
if graph hygiene remains the priority.

Minimum write packet contract:

1. Use only the `memory_related_keys_review_packet` selected edges, not raw
   `memory_orphan_candidates`.
2. Cap the first write batch to 5 to 10 edges.
3. Prefer exact Agent-Bridge project-scope pairs before global or parent-scope
   pairs.
4. Exclude generated/noisy rows: `auto_curated`, `implicit`,
   `unverified_identifier`, snapshots, alerts, work_memory, feedback, skills,
   and present_outcome.
5. Take a SQLite backup before the write.
6. Run `PRAGMA quick_check` or the project equivalent before and after.
7. Re-run topology/orphan preflight after the write.
8. Keep retrieval ranking and PageRank-like centrality disabled.
9. Record rollback as deleting the reviewed edge batch or restoring the backup.

Do not run a broad automatic orphan-linking pass yet.

## Boundary

This report did not:

- write `memory_edges`;
- write or delete durable memory rows;
- run automatic orphan linking;
- approve PageRank or centrality ranking;
- change `memory_search` order;
- change retrieval candidate sets;
- change forum thread status;
- clear `work_memory`;
- mutate runtime flags, daemon processes, schemas, tool routing, MCP profiles,
  or repository code paths.
