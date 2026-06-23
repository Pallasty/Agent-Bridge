# Trigger Recall Pre-Policy Hold Production Implementation Approval Packet Schema

Date: 2026-06-23

Scope: docs-only schema and checklist for a future approval packet that could
authorize writing a default-off production implementation candidate.

This document is not an approval packet. It does not authorize code changes,
runtime enablement, default `memory_search` changes, non-Niche exposure, memory
writes, graph writes, reindex, semantic retrieval, graph retrieval, or
coactivation for withheld hits.

## Verdict

`SCHEMA-CHECKLIST-ONLY / IMPLEMENTATION-NO-GO`

Future code remains blocked until an actual owner approval packet is created
and names the exact implementation branch, mode, surface, freshness evidence,
rollback, and scope.

## Schema Identity

Required schema for a future approval packet:

```text
agent_bridge.memory.trigger_recall.pre_policy_hold.production_implementation_approval.v0
```

Allowed approval action values:

| Action | Meaning |
|---|---|
| `approve_production_implementation_candidate_code_only` | permits writing a default-off candidate implementation, not runtime enablement |
| `request_proposal_changes` | proposal is insufficient; no code |
| `reject_production_implementation` | production implementation remains blocked |

No value in this schema may authorize runtime enablement. Runtime enablement
requires a later post-implementation review packet naming the exact candidate
commit.

## Required Packet Fields

The approval packet must include:

| Field | Required Value |
|---|---|
| `schema` | `agent_bridge.memory.trigger_recall.pre_policy_hold.production_implementation_approval.v0` |
| `owner_decision` | one allowed action value |
| `owner_identity` | non-empty board-visible owner/reviewer identity |
| `forum_post_id` | board post id for the decision |
| `memory_key` | memory key for the decision |
| `proposal_commit` | exact docs proposal commit reviewed |
| `approved_implementation_branch` | exact future candidate branch/worktree |
| `approved_mode` | `production_enforce_hold_candidate` |
| `approved_runtime_surface` | `Niche/all-profile explicit opt-in only` |
| `implementation_code_authorized` | `true` only for code-only candidate work |
| `runtime_enablement_authorized` | `false` |
| `default_memory_search_change_authorized` | `false` |
| `non_niche_exposure_authorized` | `false` |
| `memory_writes_authorized` | `false` |
| `graph_writes_authorized` | `false` |
| `semantic_retrieval_authorized` | `false` |
| `graph_retrieval_authorized` | `false` |
| `reindex_authorized` | `false` |
| `coactivation_for_withheld_hits_authorized` | `false` |
| `rollback` | concrete disable and revert procedure |
| `expires_at` | non-empty freshness deadline |

## Required Evidence Fields

The packet must embed or reference same-head evidence:

| Evidence Field | Required |
|---|---|
| `repo_head` | exact current `HEAD` |
| `origin_master` | exact `origin/master` matching `HEAD` |
| `worktree_clean` | `true` |
| `doctor_ok` | `true` |
| `doctor_fails` | `0` |
| `stale_mcp_processes` | `0` for installed `.real` under test |
| `repeatable_smoke_status` | `passed` |
| `portable_stage2_fixture_status` | `passed` |
| `aio2_baseline_audit_status` | `passed` |
| `true_hits_lost` | `0` |
| `positive_cases_held` | `0` |
| `baseline_false_hits_after_gate` | `0` |
| `raw_payload_leak_check` | `true` |
| `memory_search_mcp_called` | `false` |

If any required evidence is stale, absent, or failing, the packet must use
`request_proposal_changes` or `reject_production_implementation`.

## Required Rollback Shape

The packet must name both a runtime kill switch and binary rollback:

```text
AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1
```

and:

```text
cp <recorded-agent-bridge.real-backup> /home/pallasting/.local/bin/agent-bridge.real
/mcp reconnect
```

The candidate implementation must fail open to baseline behavior when disabled
and report `operator_disabled`.

## Approval Packet Skeleton

```json
{
  "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold.production_implementation_approval.v0",
  "owner_decision": "approve_production_implementation_candidate_code_only",
  "owner_identity": "TBD",
  "forum_post_id": "TBD",
  "memory_key": "TBD",
  "proposal_commit": "TBD",
  "approved_implementation_branch": "TBD",
  "approved_mode": "production_enforce_hold_candidate",
  "approved_runtime_surface": "Niche/all-profile explicit opt-in only",
  "implementation_code_authorized": true,
  "runtime_enablement_authorized": false,
  "default_memory_search_change_authorized": false,
  "non_niche_exposure_authorized": false,
  "memory_writes_authorized": false,
  "graph_writes_authorized": false,
  "semantic_retrieval_authorized": false,
  "graph_retrieval_authorized": false,
  "reindex_authorized": false,
  "coactivation_for_withheld_hits_authorized": false,
  "evidence": {
    "repo_head": "TBD",
    "origin_master": "TBD",
    "worktree_clean": true,
    "doctor_ok": true,
    "doctor_fails": 0,
    "stale_mcp_processes": 0,
    "repeatable_smoke_status": "passed",
    "portable_stage2_fixture_status": "passed",
    "aio2_baseline_audit_status": "passed",
    "true_hits_lost": 0,
    "positive_cases_held": 0,
    "baseline_false_hits_after_gate": 0,
    "raw_payload_leak_check": true,
    "memory_search_mcp_called": false
  },
  "rollback": {
    "disable_env": "AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1",
    "binary_rollback": "cp <recorded-agent-bridge.real-backup> /home/pallasting/.local/bin/agent-bridge.real && /mcp reconnect",
    "fail_open_required": true
  },
  "expires_at": "TBD"
}
```

## Checklist Before Accepting A Packet

A reviewer must reject or request changes if any item is false:

- packet schema matches exactly;
- owner identity is explicit;
- forum post id exists and is board-visible;
- memory key exists;
- proposal commit exists and is docs-only;
- approved implementation branch/worktree is isolated;
- runtime enablement remains false;
- default `memory_search` change remains false;
- non-Niche exposure remains false;
- write/reindex/retrieval side effects remain false;
- rollback names both disable env and binary revert;
- smoke/eval evidence is current at the packet head;
- all metric thresholds are zero where required;
- packet does not include raw query, raw keys, content, or exact local scope
  outside hashed/redacted evidence.

## Next Gate

Allowed next:

- pause for explicit owner review of this schema/checklist;
- or create a docs-only approval packet filled with `request_proposal_changes`
  or `reject_production_implementation` if production work should remain
  parked.

Still blocked:

- candidate code implementation;
- runtime enablement;
- default retrieval changes.
