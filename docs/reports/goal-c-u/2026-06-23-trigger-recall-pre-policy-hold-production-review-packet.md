# Trigger Recall Pre-Policy Hold Production Review Packet

Date: 2026-06-23

Schema: `agent_bridge.memory.trigger_recall.pre_policy_hold.production_review_packet.v0`

Scope: board-visible evidence bundle for reviewing the current
`trigger_recall_opt_in_pre_policy_hold_simulation` state before any future
production `enforce_hold` implementation proposal.

This packet does not approve production `enforce_hold`, does not implement
production behavior, does not change default `memory_search`, does not promote
Niche tools, and does not write memory, graph edges, indexes, or coactivation
state.

## Verdict

`REVIEW-PACKET-READY-NO-PRODUCTION-GO / OWNER-DECISION-REQUIRED`

Evidence is coherent enough for owner review of a future implementation
proposal. It is not sufficient to enable production `enforce_hold`.

Production `enforce_hold` remains `NO-GO` because there is no owner-approved
production implementation packet naming an exact implementation commit, approved
mode, runtime exposure, and rollback.

## Evidence Index

| Item | Value |
|---|---|
| repo head | `673978a docs(memory): plan pre-policy hold production review packet` |
| remote | `origin/master = 673978a` before this packet |
| worktree | clean before this packet |
| installed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| installed size | `67113016` bytes |
| installed sha256 | `fd7800aedef48732dd044a06b52916893cc246cf2b7f784d7d4f35f5e3a40b4a` |
| installed mtime | `2026-06-23 07:14:37 -0700` |
| implementation payload | `fbeebeb merge trigger pre-policy hold simulation candidate` |
| repeatable smoke command | `scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh` |
| regression anchor | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| parent board state | thread 105 through `#2523` |

Board references:

- `#2517`: installed-binary rollout;
- `#2518`: post-install MCP stale check;
- `#2519`: runtime smoke;
- `#2521`: runtime smoke correction;
- `#2522`: repeatable operator smoke command;
- `#2523`: production-review design plan.

Memory references:

- `trigger_recall_pre_policy_hold_post_install_mcp_stale_check_20260623`;
- `trigger_recall_pre_policy_hold_runtime_smoke_20260623`;
- `trigger_recall_pre_policy_hold_repeatable_smoke_command_20260623`;
- `trigger_recall_pre_policy_hold_production_review_design_plan_20260623`;
- `trigger_recall_pre_policy_hold_aio2_audit_evidence_20260623`.

## Runtime Surface

Current installed binary doctor:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
ok=true
fails=0
warns=1
```

Relevant pass conditions:

- wrapper intact;
- installed `.real` present;
- daemon runtime OK;
- `2 MCP server(s) - all executing current agent-bridge.real`;
- MCP tool surface check OK.

The one warning is not a trigger-recall runtime blocker:

```text
instinct_observer: rotate_observer_log
```

It is an ops hygiene warning for `/Data/agent-bridge/instinct-probe`, not stale
MCP state, binary drift, or retrieval behavior.

Active compact Codex profile still intentionally hides the Niche trigger tool.
The repeatable smoke uses a short-lived all-profile MCP subprocess:

```text
AGENT_BRIDGE_TOOL_PROFILE=all
AGENT_BRIDGE_TOOLSET=all
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE unset
```

## Smoke Results

Command:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
```

Result: passed.

```json
{
  "accepted_status": "returned_accepted",
  "accepted_store_search_called": true,
  "all_memory_search_mcp_called_false": true,
  "all_read_only": true,
  "held_status": "held_by_query_intent",
  "held_store_search_called": false,
  "implementation_commit": "fbeebeb",
  "missing_approval_status": "blocked_to_baseline",
  "missing_approval_store_search_called": true,
  "operator_disabled_status": "operator_disabled",
  "operator_disabled_store_search_called": true,
  "raw_payload_leak_check": true,
  "status": "passed",
  "tool_count_all_profile": 273,
  "tools_list_contains_target": true
}
```

Boundary fields from the same run:

```json
{
  "default_memory_search_changed": false,
  "production_enforce_hold_authorized": false,
  "memory_writes": false,
  "graph_writes": false,
  "semantic_retrieval": false,
  "graph_retrieval": false,
  "reindex": false
}
```

## Eval Results

Portable Stage-2 fixture:

```text
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
```

Result: passed with existing warnings only.

| Metric | Value |
|---|---:|
| corpus cases | `3` |
| negative controls | `4` |
| baseline/shadow R@10 | `1.000` |
| MRR | `1.000` |
| true hits lost by shadow gate | `0` |
| positive cases held | `0` |
| baseline false hits before shadow gate | `8` |
| baseline false hits after shadow gate | `0` |

Live Aio2 audit:

```text
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result: passed with existing warnings only.

| Metric | Value |
|---|---:|
| active rows | `473` |
| trigger rows | `45` |
| projected rows | `44` |
| corpus cases | `14` |
| negative controls | `8` |
| baseline/shadow R@10 | `0.857` |
| MRR | `0.786` |
| true hits lost by shadow gate | `0` |
| positive cases held | `0` |
| baseline false hits before shadow gate | `21` |
| baseline false hits after shadow gate | `0` |

Both eval paths are read-only and explicitly report default `memory_search`
unchanged.

## Boundary Table

| Boundary | Packet Value | Evidence |
|---|---|---|
| default `memory_search` unchanged | `true` | smoke + eval contracts |
| production `enforce_hold` authorized | `false` | smoke boundary + no owner approval |
| non-Niche exposure | `false` | compact profile hides Niche tool |
| MCP `memory_search` called by smoke | `false` | repeatable smoke |
| store FTS for held path by default | `false` | repeatable smoke |
| store FTS for accepted path | `true` | repeatable smoke |
| memory writes | `false` | repeatable smoke |
| graph writes | `false` | repeatable smoke |
| semantic retrieval | `false` | repeatable smoke |
| graph retrieval | `false` | repeatable smoke |
| reindex | `false` | repeatable smoke + eval contracts |
| raw query/key/content/scope leak | `false` | `raw_payload_leak_check=true` |
| coactivation for withheld hits | `false` | smoke side-effect boundary |

## Open Blockers

Production `enforce_hold` remains blocked until all are true:

- owner approves a production implementation packet;
- packet names exact implementation commit;
- packet names exact approved mode and runtime surface;
- reviewer identity is explicit and board-visible;
- rollback path is concrete and tested;
- repeatable smoke passes at the same head/install;
- portable Stage-2 fixture passes at the same head;
- live Aio2 audit passes within the freshness window;
- no default `memory_search` behavior, schema, or ordering changes;
- no non-Niche exposure;
- no writes, reindex, semantic retrieval, or graph retrieval;
- held responses remain explicit objects, never bare empty arrays.

## Owner Decision Stub

This packet intentionally leaves approval blank:

```json
{
  "owner_decision": "pending",
  "approved_mode": null,
  "approved_implementation_commit": null,
  "approved_runtime_surface": null,
  "production_enforce_hold_authorized": false,
  "default_memory_search_change_authorized": false,
  "expires_at": null,
  "rollback_confirmed": false
}
```

If an owner later approves a production implementation proposal, that decision
must be a new board-visible packet. This review packet cannot be amended into
approval by implication.

## Rollback

Current simulation rollback/disable path:

```text
unset AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE=1
```

Installed binary rollback remains the deploy-script backup path recorded by the
install rollout. Production `enforce_hold` would need its own separate disable
env and rollback evidence before implementation.

## Next Slice

Allowed next:

- owner/reviewer evaluates this packet;
- write a separate docs-only owner decision record;
- if owner chooses, design a future implementation proposal that still names
  exact commit, mode, exposure, tests, and rollback before code changes.

Still forbidden:

- implementing production `enforce_hold`;
- changing default `memory_search`;
- promoting Niche surfaces into compact/essential profiles;
- adding hidden parameters to default `memory_search`;
- writing memory or graph state;
- changing tokenizer, indexing, semantic retrieval, or graph retrieval;
- treating this packet as production approval.
