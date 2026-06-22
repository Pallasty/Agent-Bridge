# Goal C U Follow-Up - GHP-1b Orphan Reduction Selection

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: implement and deploy an optional orphan-reduction selection strategy for
explicit `related_keys` review packets.

Verdict: `landed` for read-only review packet selection and guarded
materialize dry-runs. Not an authorization to write graph edges.

## Source Anchors

| Anchor | Value |
|---|---|
| source commit | `6a177340906035f945bd88ee54a4c7fffaecc8a6` |
| source subject | `feat(memory): prioritize orphan reduction in related keys review` |
| deployed HEAD | `eef4de7` |
| deployed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| deployed sha256 | `798f58951d76c86a302883e93d1ad3531f180f8da3944c7f999199cc2000cfbb` |
| deployed version | `ab-bridge 0.1.0` |
| deployed source | `origin/master @ eef4de7` |
| rollback binary | `/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-eef4de7-20260622T032539` |

## What Changed

`memory_related_keys_review_packet` now accepts:

```json
{"selection_strategy": "preserve_order"}
```

or:

```json
{"selection_strategy": "orphan_reduction"}
```

The default remains `preserve_order`, preserving historical scan-order
behavior. `orphan_reduction` sorts already-safe explicit `related_keys`
candidates by how many current visible-subgraph orphan nodes they touch, then
keeps the existing caps and filters:

- generated-noise filters remain active;
- exact/compatible scope filters remain active;
- max-pairs, max-outbound, and max-inbound caps remain active;
- no inferred content linking is introduced;
- no search ranking or runtime candidate set changes.

The guarded `memory_related_keys_materialize` path also accepts the same
`selection_strategy` argument so a later dry-run or approved tiny write batch
can reuse the reviewed ordering. It still defaults to `dry_run=true` and still
requires `apply_confirmation='materialize_related_keys'` before any write.

## Verification

Command:

```bash
cargo test -p ab-bridge --lib memory_related_keys -- --nocapture
```

Result:

| Check | Result |
|---|---|
| related_keys preflight tests | pass |
| guarded materialize cap tests | pass |
| exact-scope review/materialize tests | pass |
| orphan-reduction planner test | pass |
| orphan-reduction review packet test | pass |
| total selected tests | `10 passed` |

Existing unrelated warnings were observed:

- `mixed_script_confusables` for the existing `β` test name in
  `crates/store/src/sqlite.rs`;
- existing private-interface warning for `ToolPolicy`;
- existing release warnings around retired Option-E helpers.

## Deploy And Runtime

Deployment:

```bash
scripts/deploy_from_master.sh --yes
```

Result:

- release build completed in `6m48s`;
- feature gate passed;
- binary deployed to `/home/pallasting/.local/bin/agent-bridge.real`;
- user services were restarted:
  - `agent-bridge-daemon.service`;
  - `agent-bridge-daemon-http.service`;
  - `agent-bridge-palace.service`.

Post-deploy checks:

| Check | Result |
|---|---|
| `agent-bridge.real doctor --json` | `ok=true`, `fails=0`, `warns=1` |
| daemon-http `http://127.0.0.1:7878/healthz` | `ok` |
| Palace `http://127.0.0.1:7979/healthz` | `ok` |
| `mcp_lifecycle_digest` | lifecycle `ready`, readiness `ready`, runtime health `ready` |

The single doctor warning is expected immediately after deploy: two running MCP
stdio servers still point at the old deleted `.real`. A Codex/Cursor MCP
reconnect is required before this current client can call the newly extended MCP
schema directly.

## Evidence From GHP-1b Baseline

Before this implementation, the exact-scope default review packet selected 20
semantically coherent explicit `related_keys` edges but reduced `0` current
visible-subgraph orphans:

| Metric | Default review packet |
|---|---:|
| visible total | 139 |
| current edge pairs | 287 |
| current orphans | 35 |
| safe candidates before caps | 100 |
| selected edges | 20 |
| orphans reduced by selected | 0 |

The local read-only orphan-prioritized calculation over the same exact scope
found a better first review batch:

| Metric | Orphan-prioritized calculation |
|---|---:|
| visible total | 139 |
| current edge pairs | 287 |
| current orphans | 35 |
| safe candidates | 100 |
| candidates touching orphan nodes | 35 |
| selected edges under 20-pair cap | 20 |
| orphan nodes covered by selected | 23 |

That result is the reason for making the strategy explicit in the MCP tool
instead of treating it as an ad hoc report-only calculation.

## Live MCP Reconnect Check

After MCP reconnect, this session ran the live read-only comparison with the
new `selection_strategy` field visible in the MCP schema.

Common inputs:

```json
{
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "scope_mode": "local_only",
  "scope_filter": "exact",
  "selection_strategy": "preserve_order",
  "max_pairs": 20,
  "max_records": 1000,
  "preview_chars": 80
}
```

Result:

| Metric | `preserve_order` | `orphan_reduction` |
|---|---:|---:|
| loaded records | 438 | 438 |
| visible total | 140 | 140 |
| current edge pairs | 288 | 288 |
| current orphans | 35 | 35 |
| safe candidates before caps | 101 | 101 |
| selected edges | 20 | 20 |
| orphan candidate nodes selected | 0 | 22 |
| orphans reduced by selected | 0 | 22 |
| projected orphans after selected | 35 | 13 |

Safety flags from both live packets remained read-only: no memory writes, no
graph-edge writes, no search-order change, no production retrieval-order change,
no PageRank/centrality rank prior, and no automatic orphan linking.

This validates the intended behavior: `preserve_order` remains the stable
compatibility baseline, while `orphan_reduction` produces a materially better
first 20-edge review packet for graph hygiene.

The next safe step from this live comparison was a guarded
`memory_related_keys_materialize` dry-run, not a write. In the active compact
MCP tool profile, that materialize tool is intentionally not exposed; the later
section below records a one-shot all-profile subprocess dry-run that kept
`dry_run=true` and did not change the active Codex MCP surface.

The exact `orphan_reduction` invocation used:

```json
{
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "scope_mode": "local_only",
  "scope_filter": "exact",
  "selection_strategy": "orphan_reduction",
  "max_pairs": 20,
  "max_records": 1000,
  "preview_chars": 80
}
```

## Guarded Materialize Dry-Run

After a later Codex restart and repository sync, the local checkout was updated
to `origin/master @ 9a0e3d5` for the materialize dry-run. Before committing this
report update, the checkout was fast-forwarded again to `origin/master @
bb587b6`. Those remote advances were report/example work for trigger-aware
recall diagnostics, not runtime behavior changes to the GHP-1b MCP tool
implementation. Verification after the final sync:

```bash
cargo check -p ab-bridge --examples
~/.local/bin/agent-bridge.real doctor --json
```

Result:

| Check | Result |
|---|---|
| examples compile | pass |
| doctor | `ok=true`, `fails=0`, `warns=0` |
| final base before this report commit | `HEAD == origin/master == bb587b6` |

The compact Codex MCP profile intentionally does not expose
`memory_related_keys_materialize`, because it is write-capable when
`dry_run=false`. To validate the next step without changing the active MCP
surface, a one-shot local MCP stdio subprocess was launched with
`AGENT_BRIDGE_TOOL_PROFILE=all`, then called with `dry_run=true` only.

Common materialize dry-run inputs:

```json
{
  "dry_run": true,
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "scope_mode": "local_only",
  "scope_filter": "exact",
  "max_records": 1000,
  "max_edges": 20,
  "max_outbound_per_source": 3,
  "max_inbound_per_target": 3,
  "preview_chars": 0
}
```

Result under the materializer's real default skip set, which excludes
`session_handoff` rows:

| Metric | `preserve_order` | `orphan_reduction` |
|---|---:|---:|
| dry run | true | true |
| blocked | false | false |
| linked | 0 | 0 |
| loaded records | 438 | 438 |
| safe candidates before caps | 90 | 90 |
| current orphans | 32 | 32 |
| selected edges | 20 | 20 |
| orphan candidate nodes selected | 1 | 22 |
| orphans reduced by selected | 1 | 22 |
| projected orphans after selected | 31 | 10 |

This confirms the reviewed ordering still matters under the actual guarded
writer plan: with the same 20-edge cap and no writes, `orphan_reduction` picks a
materially better first batch than the compatibility baseline.

Post-dry-run topology was unchanged at the durable read-only preflight level:
`non_skill_active_total=140`, `orphan_count=45`, `orphan_fraction=0.321`,
`p4_evolved_coverage=95`, and `pagerank_readiness=hub_risk_cap_centrality_boost`.
No graph edge, memory row, ranking, search-order, or candidate-set write was
performed.

## Non-Authorizations

This report does not authorize:

- `memory_related_keys_materialize` with `dry_run=false`;
- graph edge writes;
- automatic orphan linking;
- memory row rewrites;
- PageRank, centrality, or graph-neighbor live ranking;
- production search-order changes;
- candidate-set expansion;
- new MCP tools;
- executor or auto-approval behavior.

Rollback for the code:

```bash
git revert 6a177340906035f945bd88ee54a4c7fffaecc8a6
cp /home/pallasting/.local/bin/agent-bridge.real.bak-deploy-eef4de7-20260622T032539 /home/pallasting/.local/bin/agent-bridge.real
```

Then reconnect MCP clients.
