# Goal C U Follow-Up - GHP-1b Tiny Write Review Packet

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: review the first tiny explicit `related_keys` graph materialization batch
suggested by GHP-1b.

Verdict: `ready_for_decision`, not `authorized_to_write`.

This packet is the decision surface for a later `dry_run=false` call. It does
not perform a write and does not authorize search ranking, PageRank, centrality,
candidate-set expansion, or automatic orphan linking.

## Source Anchors

| Anchor | Value |
|---|---|
| implementation commit | `6a177340906035f945bd88ee54a4c7fffaecc8a6` |
| dry-run evidence commit | `55ac145 docs: record ghp1b materialize dry-run` |
| base before this packet | `origin/master @ 55ac145` |
| report dependency | `docs/reports/goal-c-u/2026-06-22-ghp1b-orphan-reduction-selection.md` |
| state DB | `/home/pallasting/.local/share/agent-bridge/state.db` |

## Dry-Run Inputs

The candidate batch was produced by a one-shot local MCP stdio subprocess with
`AGENT_BRIDGE_TOOL_PROFILE=all`, because the active compact Codex MCP profile
intentionally hides the write-capable materializer. The tool call used
`dry_run=true`.

```json
{
  "dry_run": true,
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "scope_mode": "local_only",
  "scope_filter": "exact",
  "selection_strategy": "orphan_reduction",
  "max_records": 1000,
  "max_edges": 20,
  "max_outbound_per_source": 3,
  "max_inbound_per_target": 3,
  "preview_chars": 0
}
```

The materializer's real default filters were active, including exclusion of
`session_handoff` rows.

## Dry-Run Result

| Metric | Value |
|---|---:|
| loaded records | 438 |
| safe candidate pairs before caps | 91 |
| current orphans | 32 |
| selected edges | 20 |
| orphan candidate nodes selected | 22 |
| orphans reduced by selected | 22 |
| projected orphans after selected | 10 |
| blocked | false |
| linked | 0 |

Note: safe candidate count was `90` before this session saved the durable
dry-run memory, and `91` afterward. The selected 20-edge batch and orphan
reduction stayed stable.

Selected edge list SHA-256:

```text
940c584a45386ba13f59dae136488a1b1c81861a6e92693a5008cf55375fb5ea
```

## Selected Batch

1. `agent_bridge_deployed_runtime_executor_design_preflight_20260616` ->
   `agent_bridge_deployed_latest_20260616` (`decision -> decision`)
2. `biocortex_post_runtime_multi_case_live_candidate_20260613` ->
   `biocortex_post_runtime_live_candidate_runner_20260613`
   (`decision -> decision`)
3. `biocortex_post_runtime_live_candidate_runner_20260613` ->
   `biocortex_post_runtime_live_candidate_fixture_20260613`
   (`decision -> context`)
4. `biocortex_post_runtime_live_candidate_runner_20260613` ->
   `biocortex_post_runtime_evidence_backed_decision_20260613`
   (`decision -> context`)
5. `biocortex_post_runtime_live_candidate_fixture_20260613` ->
   `biocortex_post_runtime_evidence_backed_decision_20260613`
   (`context -> context`)
6. `biocortex_post_runtime_live_candidate_fixture_20260613` ->
   `biocortex_post_decision_runtime_readiness_20260613`
   (`context -> context`)
7. `biocortex_post_runtime_evidence_backed_decision_20260613` ->
   `biocortex_post_decision_runtime_readiness_20260613`
   (`context -> context`)
8. `biocortex_post_runtime_evidence_backed_decision_20260613` ->
   `biocortex_runtime_influence_authorization_decision_20260613`
   (`context -> decision`)
9. `biocortex_post_decision_runtime_readiness_20260613` ->
   `biocortex_runtime_influence_authorization_decision_20260613`
   (`context -> decision`)
10. `biocortex_post_decision_runtime_readiness_20260613` ->
    `biocortex_runtime_influence_review_request_20260613`
    (`context -> context`)
11. `biocortex_runtime_influence_authorization_decision_20260613` ->
    `biocortex_runtime_influence_review_request_20260613`
    (`decision -> context`)
12. `biocortex_opt_in_runtime_readiness_mcp_surface_20260612` ->
    `biocortex_opt_in_runtime_readiness_packet_20260612`
    (`decision -> decision`)
13. `biocortex_opt_in_runtime_readiness_packet_20260612` ->
    `biocortex_opt_in_downstream_aggregate_decision_packet_20260612`
    (`decision -> decision`)
14. `sepl_p0_resource_versions_committed_20260601` ->
    `research_three_resource_value_mapping_to_proposals_20260601`
    (`decision -> decision`)
15. `observation_linux_codex_avatar_renderer_probe_20260601` ->
    `decision_linux_codex_avatar_renderer_v26_20260601`
    (`observation -> decision`)
16. `decision_linux_codex_avatar_native_transparent_backend_20260601` ->
    `decision_linux_codex_avatar_transparency_backend_20260601`
    (`decision -> decision`)
17. `decision_linux_codex_avatar_native_sprite_rendering_20260601` ->
    `decision_linux_codex_avatar_native_transparent_backend_20260601`
    (`decision -> decision`)
18. `decision_linux_codex_avatar_native_sprite_rendering_20260601` ->
    `decision_linux_codex_avatar_transparency_backend_20260601`
    (`decision -> decision`)
19. `aio2_kilo_cli_available_20260530` ->
    `agentbridge_remote_session_steer_gap_20260529`
    (`context -> decision`)
20. `agentbridge_remote_session_steer_gap_20260529` ->
    `lesson_macos_atomic_deploy_running_binary_20260530`
    (`decision -> lesson`)

## Manual Semantic Review

This review checks only whether the 20 proposed `relates` edges are reasonable
same-project links from already-explicit `related_keys`. It does not reinterpret
the edge type as causality, dependency, approval, ranking authority, or runtime
influence.

Result:

| Check | Result |
|---|---:|
| selected edges reviewed | 20 |
| semantic pass | 20 |
| semantic reject | 0 |
| needs split or reclassify before tiny write | 0 |

Reviewed groups:

| Edges | Assessment |
|---|---|
| 1 | Deployment-to-deployment lineage; the runtime executor design preflight deploy is directly related to the latest deployed Agent-Bridge state. |
| 2-11 | BioCortex post-runtime evidence/readiness chain; the records form a tightly scoped progression from live-candidate runner/fixtures through evidence-backed readiness, review request, and authorization decision. |
| 12-13 | BioCortex opt-in runtime-readiness packet chain; MCP surface, readiness packet, and downstream aggregate decision packet are directly adjacent artifacts. |
| 14 | SEPL P0 resource-version implementation is linked to the earlier three-resource value-mapping proposal that motivated the SEPL/RSPL lane. |
| 15-18 | Linux Codex avatar renderer chain; live probe, v26 renderer decision, transparent backend, and native sprite rendering are same-lane implementation/decision records. |
| 19-20 | Remote-session steering chain; Kilo CLI availability supports the remote steering gap lane, and that delivered remote-control lane is related to the atomic deploy running-binary lesson. |

Cautions retained:

- all edges must remain `relates`;
- the BioCortex cluster is dense, so the 20-edge cap and inbound/outbound caps
  should not be relaxed for this batch;
- this semantic pass is only for the listed hash-locked tiny batch and does not
  approve later candidate-set expansion.

Manual review verdict: `semantic_review_passed_for_tiny_batch`, still
`not_authorized_to_write`.

## Pre-Write Gates

These checks must all pass immediately before any future `dry_run=false` call:

| Gate | Required Result |
|---|---|
| repo status | clean, no unpushed code/report changes |
| service health | `agent-bridge.real doctor --json` has `ok=true`, `fails=0`, `warns=0` |
| SQLite integrity | read-only `PRAGMA quick_check` returns `ok` |
| rescue snapshot | `agent-bridge.real rescue-snapshot --canonical --json` succeeds and artifact path is recorded |
| fresh dry-run | selected-edge hash matches `940c584a45386ba13f59dae136488a1b1c81861a6e92693a5008cf55375fb5ea` |
| write cap | `max_edges` remains `20`; inbound/outbound caps remain `3` |
| profile isolation | use a one-shot all-profile MCP subprocess; do not expose materializer in compact Codex profile |

The current system lacks the `sqlite3` CLI, so the read-only quick check in this
session used Python's standard library with `mode=ro`:

```bash
python3 -c 'import sqlite3; p="/home/pallasting/.local/share/agent-bridge/state.db"; con=sqlite3.connect(f"file:{p}?mode=ro", uri=True); print(con.execute("PRAGMA quick_check").fetchone()[0]); con.close()'
```

Observed result: `ok`.

## Pre-Write Gate Attempt After MCP Restart

After the remaining stale Codex/Cursor MCP session was restarted, the pre-write
gates were rerun on 2026-06-22 before any `dry_run=false` call.

Result:

| Gate | Observed Result |
|---|---|
| repo status | clean; `HEAD == origin/master == b84a9794a13e9ce711a6c279a47d2057951dbb13` |
| service health | `agent-bridge.real doctor --json`: `ok=true`, `fails=0`, `warns=0` |
| SQLite integrity | read-only `PRAGMA quick_check`: `ok` |
| rescue snapshot | succeeded; recovery dir `/home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1136` |
| profile isolation | one-shot all-profile MCP subprocess; compact Codex profile still does not expose `memory_related_keys_materialize` |
| fresh dry-run | `dry_run=true`, `blocked=false`, `linked=0`, `write_errors=[]` |
| write cap | `max_edges=20`, inbound/outbound caps `3` |
| selected edge sequence | same ordered 20 edges as this packet |
| selected-edge hash | blocked: packet hash algorithm was not recorded and could not be reproduced from common normalizations |

Fresh dry-run metrics:

| Metric | Value |
|---|---:|
| loaded records | 441 |
| safe candidate pairs before caps | 94 |
| current orphans | 33 |
| selected edges | 20 |
| orphan candidate nodes selected | 22 |
| orphans reduced by selected | 22 |
| projected orphans after selected | 11 |

The ordered selected edge list matched this packet exactly, but the published
hash `940c584a45386ba13f59dae136488a1b1c81861a6e92693a5008cf55375fb5ea` lacks a
recorded canonicalization rule. Recomputed hashes over common formats
(`from -> to`, `from -> to (kind)`, tab/pipe-delimited rows, compact JSON pair
arrays, compact JSON objects, and the Markdown selected-batch block) did not
match it.

Gate verdict: `blocked_before_write_due_to_unreproducible_hash_gate`.

No `dry_run=false` call was made. No graph edge, memory row, ranking,
search-order, candidate-set, or automatic orphan-linking change was performed.

## Apply Shape If Later Approved

If and only if the above gates pass and the batch is explicitly approved, the
write call should be identical to the dry-run call except:

```json
{
  "dry_run": false,
  "apply_confirmation": "materialize_related_keys"
}
```

Expected immediate write result:

- `blocked=false`;
- `linked=20`;
- `write_errors=[]`.

Any mismatch blocks the run and requires rollback/review.

## Post-Write Verification If Later Approved

Immediately after a future approved write:

1. run `agent-bridge.real doctor --json`;
2. run read-only `PRAGMA quick_check`;
3. rerun `memory_related_keys_preflight` or `memory_related_keys_review_packet`
   with exact project scope;
4. rerun `memory_graph_topology` with the same durable skip set;
5. record whether materializer-current orphans moved from `32` toward `10`;
6. record whether topology orphan count changed and whether hub risk remains
   capped;
7. post the result to forum thread #105 and save durable memory.

## Rollback If Later Approved

Preferred rollback is restoring the rescue snapshot captured immediately before
the write. If restoration is not appropriate, delete only the reviewed
`relates` edge batch listed above, then rerun `PRAGMA quick_check` and topology.

Rollback must not delete memory rows, alter `related_keys`, change retrieval
ranking, or run automatic orphan linking.

## Non-Authorizations

This packet does not authorize:

- running `dry_run=false`;
- graph edge writes;
- memory row writes;
- search-order or production retrieval-order changes;
- PageRank, centrality, or graph-neighbor rank priors;
- candidate-set expansion;
- automatic orphan linking;
- changing the compact Codex MCP profile;
- executor or auto-approval behavior.
