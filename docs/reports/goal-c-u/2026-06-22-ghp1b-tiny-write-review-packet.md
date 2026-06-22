# Goal C U Follow-Up - GHP-1b Tiny Write Review Packet

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: review the first tiny explicit `related_keys` graph materialization batch
suggested by GHP-1b.

Verdict: `approved_write_applied`.

This packet began as the decision surface for a later `dry_run=false` call. It
now also records the owner-approved tiny write that materialized exactly the
hash-locked 20-edge batch. The write did not authorize search ranking,
PageRank, centrality, candidate-set expansion, or automatic orphan linking.

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

Selected edge list SHA-256, canonical v1:

```text
4868930845e953281e1bef2c30613c18cb0d42c91a886443b6c36bf8f030e9c0
```

Canonicalization rule v1:

1. Preserve selected edge order exactly as returned by
   `memory_related_keys_materialize`.
2. For each selected edge, keep only `from_key`, `kind_pair`, and `to_key`.
3. Serialize as a JSON array of objects with lexicographically sorted object
   keys.
4. Use compact JSON separators: comma `,` and colon `:`, with no extra
   whitespace.
5. Compute SHA-256 over the resulting UTF-8 bytes.

The earlier packet hash
`940c584a45386ba13f59dae136488a1b1c81861a6e92693a5008cf55375fb5ea` is retained
only as historical evidence from the first packet draft; its canonicalization
rule was not recorded and later could not be reproduced, so it must not be used
as a write gate.

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
| fresh dry-run | selected-edge hash v1 matches `4868930845e953281e1bef2c30613c18cb0d42c91a886443b6c36bf8f030e9c0` |
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

## Canonical Hash Gate Repair

The selected-edge hash gate was repaired by defining `selected_edge_hash_v1`
with the canonicalization rule above. A fresh all-profile MCP materialize
dry-run was run with `dry_run=true` only and the same exact scope/caps.

Result:

| Check | Observed Result |
|---|---|
| materializer visibility | available only in one-shot `AGENT_BRIDGE_TOOL_PROFILE=all` MCP subprocess |
| dry run | `true` |
| blocked | `false` |
| linked | `0` |
| write errors | `[]` |
| selected edge sequence | same ordered 20 edges as this packet |
| canonical JSON bytes | `3385` |
| selected-edge hash v1 | `4868930845e953281e1bef2c30613c18cb0d42c91a886443b6c36bf8f030e9c0` |

Fresh dry-run metrics after the hash-gate repair:

| Metric | Value |
|---|---:|
| loaded records | 443 |
| safe candidate pairs before caps | 94 |
| current orphans | 32 |
| selected edges | 20 |
| orphan candidate nodes selected | 22 |
| orphans reduced by selected | 22 |
| projected orphans after selected | 10 |

Gate verdict: `hash_gate_repaired_and_reproducible`, still
`not_authorized_to_write`.

No `dry_run=false` call was made. No graph edge, memory row, ranking,
search-order, candidate-set, or automatic orphan-linking change was performed.

## Approved Write Applied

The owner explicitly approved the tiny write on 2026-06-22 with:
`批准执行 GHP-1b 20-edge 写入`.

Final pre-write gates:

| Check | Result |
|---|---|
| primary checkout | clean and aligned with `origin/master` |
| deployed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| deployed binary SHA-256 | `38e981234ea1ec718d642f4d85b6526df11d68deb3172dfdc91e9ac90ff5366e` |
| doctor | `ok=true`, `fails=0`, `warns=1` |
| doctor warning | one separate stale old Codex MCP process; current session was on current `.real` |
| SQLite `PRAGMA quick_check` | `ok` |
| rescue snapshot | `/home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1306` |
| rescue marker | `fnv1a16:09f66f35910cda1e` |

Immediately before the write, the materializer was rerun with `dry_run=true`
and the same exact scope/caps. The canonical selected-edge hash still matched
`selected_edge_hash_v1`.

| Metric | Pre-Write Dry-Run |
|---|---:|
| loaded records | 447 |
| safe candidate pairs before caps | 94 |
| current orphans | 32 |
| selected edges | 20 |
| orphan candidate nodes selected | 22 |
| orphans reduced by selected | 22 |
| projected orphans after selected | 10 |
| selected-edge hash v1 | `4868930845e953281e1bef2c30613c18cb0d42c91a886443b6c36bf8f030e9c0` |

The approved write call used the same arguments as the dry-run plus:

```json
{
  "dry_run": false,
  "apply_confirmation": "materialize_related_keys"
}
```

Write result:

| Metric | Result |
|---|---:|
| dry run | false |
| blocked | false |
| linked | 20 |
| write errors | `[]` |
| selected edges | 20 |
| selected-edge hash v1 | `4868930845e953281e1bef2c30613c18cb0d42c91a886443b6c36bf8f030e9c0` |

Immediate post-write dry-run, using the same exact scope/caps:

| Metric | Post-Write Dry-Run |
|---|---:|
| loaded records | 447 |
| safe candidate pairs before caps | 74 |
| current orphans | 10 |
| selected edges | 20 |
| orphan candidate nodes selected | 3 |
| orphans reduced by selected | 3 |
| projected orphans after selected | 7 |
| next-batch selected-edge hash v1 | `49ce7fafd74fed3b2479d8da979883c2484929b570c59b3fa26ee3c7639a7576` |

SQLite read-only verification:

| Check | Result |
|---|---|
| `PRAGMA quick_check` after write | `ok` |
| latest `memory_edges.created_at` | `1782133636` (`2026-06-22T13:07:16+00:00`) |
| latest batch type/count | `relates`: `20` |
| total `memory_edges` rows after write | `546` |

Read-only topology note: the broad durable `memory_graph_topology` and
`memory_orphan_inventory` tools use a wider denominator than the materializer's
exact-scope orphan-reduction gate. They reported `eligible_orphans=23` after
the write. The materializer gate metric for this approved exact-scope batch
moved from `current_orphans=32` to `current_orphans=10`.

## Applied Write Shape

The approved write call was identical to the hash-locked dry-run call except:

```json
{
  "dry_run": false,
  "apply_confirmation": "materialize_related_keys"
}
```

Observed immediate write result:

- `blocked=false`;
- `linked=20`;
- `write_errors=[]`.

No mismatch was observed.

## Post-Write Verification Completed

Immediately after the approved write:

1. `agent-bridge.real doctor --json` was run before the write;
2. read-only `PRAGMA quick_check` was run before and after the write;
3. `memory_related_keys_materialize` was rerun in dry-run mode with exact
   project scope after the write;
4. `memory_graph_topology` and `memory_orphan_inventory` were run with the same
   durable skip set;
5. materializer-current orphans moved from `32` to `10`;
6. topology/orphan inventory used a broader denominator and reported
   `eligible_orphans=23`;
7. the result was posted to forum thread #105.

## Rollback Anchor

Preferred rollback is restoring the rescue snapshot captured immediately before
the write:
`/home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1306`
(`fnv1a16:09f66f35910cda1e`). If restoration is not appropriate, delete only
the reviewed `relates` edge batch with `created_at=1782133636`, then rerun
`PRAGMA quick_check` and topology.

Rollback must not delete memory rows, alter `related_keys`, change retrieval
ranking, or run automatic orphan linking.

## Non-Authorizations

This packet records the approved 20-edge write only. It does not authorize:

- additional `dry_run=false` calls;
- additional graph edge writes;
- memory row writes;
- search-order or production retrieval-order changes;
- PageRank, centrality, or graph-neighbor rank priors;
- candidate-set expansion;
- automatic orphan linking;
- changing the compact Codex MCP profile;
- executor or auto-approval behavior.
