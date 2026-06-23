# Trigger Recall Pre-Policy Hold Repeatable Smoke Command

Date: 2026-06-23

Scope: add and verify a repeatable operator smoke command for the installed
`trigger_recall_opt_in_pre_policy_hold_simulation` Niche MCP surface.

This slice only makes the previously manual runtime smoke reproducible. It does
not authorize production `enforce_hold`, default `memory_search` changes,
non-Niche exposure, semantic retrieval, graph retrieval, memory writes, graph
writes, coactivation, or reindex.

## Decision

`APPROVED-AS-READ-ONLY-OPERATOR-SMOKE / NICHE-ONLY / PRODUCTION-STILL-BLOCKED`

The one-shot runtime smoke from
`2026-06-23-trigger-recall-pre-policy-hold-runtime-smoke.md` is now available
as the main operator command:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
```

and a compatibility alias:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke-mcp.sh
```

The script defaults to the installed binary:

```text
${HOME}/.local/bin/agent-bridge.real
```

and can be pointed at another binary with:

```text
AB_BIN=/path/to/agent-bridge.real \
  scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
```

## Smoke Contract

The script starts a short-lived MCP subprocess with:

```text
AGENT_BRIDGE_TOOL_PROFILE=all
AGENT_BRIDGE_TOOLSET=all
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE unset
```

It then verifies:

- `tools/list` exposes `trigger_recall_opt_in_pre_policy_hold_simulation`;
- the target schema includes `approval_packet`, `query`, `per_call_opt_in`, and
  `include_baseline_counts`;
- approved held query returns `held_by_query_intent` and does not call store FTS
  by default;
- approved accepted query returns `returned_accepted` and may call store FTS
  directly;
- missing approval packet returns `blocked_to_baseline`;
- operator-disabled request returns `operator_disabled`;
- every path reports `read_only=true`;
- every path reports `memory_search_mcp_called=false`;
- raw query text and the exact local project scope are absent from returned
  payloads;
- production `enforce_hold` remains unauthorized.

## Verification Run

Command:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke-mcp.sh
```

Result:

```json
{
  "ab_bin": "/home/pallasting/.local/bin/agent-bridge.real",
  "accepted_status": "returned_accepted",
  "accepted_store_search_called": true,
  "all_memory_search_mcp_called_false": true,
  "all_read_only": true,
  "boundaries": {
    "default_memory_search_changed": false,
    "graph_retrieval": false,
    "graph_writes": false,
    "memory_writes": false,
    "production_enforce_hold_authorized": false,
    "reindex": false,
    "semantic_retrieval": false
  },
  "held_status": "held_by_query_intent",
  "held_store_search_called": false,
  "implementation_commit": "fbeebeb",
  "missing_approval_status": "blocked_to_baseline",
  "missing_approval_store_search_called": true,
  "operator_disabled_status": "operator_disabled",
  "operator_disabled_store_search_called": true,
  "raw_payload_leak_check": true,
  "schema": "agent_bridge.trigger_recall.pre_policy_hold_runtime_smoke_script.v0",
  "status": "passed",
  "tool_count_all_profile": 273,
  "tools_list_contains_target": true
}
```

## Boundaries

This command is safe to rerun as a read-only installed-binary smoke. It is not a
deployment command, not a production approval packet, and not a default retrieval
change.

Production `enforce_hold` remains blocked until a separate owner-approved packet
names exact production metrics, rollback, exposure surface, and default
`memory_search` invariants.
