# Trigger Recall Pre-Policy Hold Runtime Smoke

Date: 2026-06-23

Scope: installed-binary runtime smoke for the already-merged and already
installed `trigger_recall_opt_in_pre_policy_hold_simulation` Niche MCP surface.

This report records a read-only smoke only. It does not authorize production
`enforce_hold`, default `memory_search` changes, semantic or graph retrieval,
memory writes, graph writes, reindex, or exposure outside the `all`/Niche tool
profile.

## Verdict

`RUNTIME-SMOKE-PASS / NICHE-ONLY / PRODUCTION-ENFORCE-HOLD-STILL-BLOCKED`

## Preconditions

Repository and binary state:

```text
base before this report = b1aa844 docs(memory): record macos pre-policy hold rollout
installed binary = /home/pallasting/.local/bin/agent-bridge.real
```

Post-reconnect doctor:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
ok=true
fails=0
warns=0
mcp_servers=2 MCP server(s) all executing current agent-bridge.real
```

Current Codex profile remains compact/essential:

```text
client=codex
toolset=codex-essential
tool_profile_env=essential
exposed_tool_count=94
```

That active session profile still intentionally hides the Niche trigger tool.
The runtime smoke therefore used a short-lived installed-binary MCP subprocess
with:

```text
AGENT_BRIDGE_TOOL_PROFILE=all
AGENT_BRIDGE_TOOLSET=all
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE unset
```

## Smoke Method

The subprocess performed:

1. MCP `initialize`.
2. MCP `tools/list`.
3. Schema presence check for
   `trigger_recall_opt_in_pre_policy_hold_simulation`.
4. Four read-only `tools/call` cases:
   - approved held query with default count audit disabled;
   - approved accepted query;
   - missing approval packet fail-open path;
   - operator disabled fail-open path.

The approval packet used the exact pre-policy hold schema and required fields:

```text
schema=agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0
packet_status=approved_for_pre_policy_hold_simulation
approved_mode=pre_policy_hold_simulation
implementation_commit=fbeebeb
regression_anchor=aio2_trigger_recall_baseline_acceptance_shadow_20260623
default_memory_search_unchanged=true
raw_query_included=false
raw_keys_included=false
content_included=false
rollback present
```

## Result Summary

```json
{
  "accepted_status": "returned_accepted",
  "accepted_store_search_called": true,
  "all_memory_search_mcp_called_false": true,
  "all_read_only": true,
  "held_status": "held_by_query_intent",
  "held_store_search_called": false,
  "missing_approval_status": "blocked_to_baseline",
  "operator_disabled_status": "operator_disabled",
  "raw_payload_leak_check": true,
  "tool_count_all_profile": 273,
  "tools_list_contains_target": true
}
```

## Interpretation

- The installed binary exposes the Niche surface under
  `AGENT_BRIDGE_TOOL_PROFILE=all`.
- The active compact Codex profile still intentionally hides the surface.
- The held path returns a status packet and does not call store FTS by default.
- The accepted path may call store FTS directly and returns only redacted hit
  summaries.
- Missing approval and operator-disabled paths fail open to baseline behavior.
- All paths report `memory_search_mcp_called=false`.
- All inspected packets report `read_only=true`.
- Raw query text and the exact local project scope were not present in the
  returned payloads.

## Boundaries Preserved

This smoke does not authorize:

- default `memory_search` ordering, schema, or behavior changes;
- production `enforce_hold`;
- non-Niche exposure;
- semantic or graph retrieval;
- memory writes;
- graph writes;
- coactivation recording;
- reindexing;
- automatic runtime rollout from the compact Codex profile.

## Next Gate

The next safe slice is a docs-first runtime review packet that decides whether
the current Niche/all-profile behavior is sufficient, or whether a narrower
operator-facing smoke command should be added for repeatability.

Production `enforce_hold` remains blocked until a separate owner-approved
production packet names exact metrics, rollback, exposure surface, and default
`memory_search` invariants.
