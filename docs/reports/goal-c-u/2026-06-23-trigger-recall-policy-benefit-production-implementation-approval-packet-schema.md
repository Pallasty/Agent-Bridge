# Trigger Recall Policy-Benefit Production Implementation Approval Packet Schema

Date: 2026-06-23

Scope: docs-only schema and checklist for a future owner packet that could
reopen default-off trigger-recall production implementation candidate work after
the repaired live Mac `policy_benefit_eval.v0` review.

This document is not an approval packet. It does not authorize code changes,
runtime enablement, production `enforce_hold`, default `memory_search` changes,
non-Niche exposure, memory writes, graph writes, reindex, semantic retrieval,
graph retrieval, or coactivation for withheld hits.

## Verdict

`SCHEMA-CHECKLIST-ONLY / IMPLEMENTATION-NO-GO`

Future code remains blocked until an actual owner approval packet is created
and names the exact reviewed proposal, implementation branch, candidate mode,
runtime surface, freshness evidence, rollback, and scope.

The current owner direction "continue" is treated as permission to advance this
docs-only gate. It is not interpreted as production implementation approval.

## Schema Identity

Required schema for a future policy-benefit production implementation approval
packet:

```text
agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_approval.v0
```

Allowed `owner_decision` values:

| Value | Meaning |
|---|---|
| `approve_candidate_code_only` | permits writing a default-off candidate implementation, not runtime enablement |
| `request_proposal_changes` | proposal or evidence is insufficient; no code |
| `reject_production_implementation` | production implementation remains parked |

No value in this schema may authorize runtime enablement. Runtime enablement
requires a later post-implementation review packet naming the exact candidate
commit and fresh verification evidence.

## Required Packet Fields

The approval packet must include:

| Field | Required Value |
|---|---|
| `schema` | `agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_approval.v0` |
| `owner_decision` | one allowed value |
| `owner_identity` | non-empty board-visible owner/reviewer identity |
| `forum_post_id` | board post id for the decision |
| `memory_key` | memory key for the decision |
| `proposal_design_commit` | exact docs proposal commit reviewed |
| `policy_benefit_review_packet_commit` | exact review packet commit |
| `policy_benefit_repair_commit` | exact repair commit |
| `approved_implementation_branch` | exact future candidate branch/worktree |
| `approved_mode` | `audit_only_candidate` or `pre_policy_hold_candidate` |
| `approved_runtime_surface` | `Niche/all-profile explicit opt-in only` |
| `implementation_code_authorized` | `true` only when `owner_decision=approve_candidate_code_only` |
| `runtime_enablement_authorized` | `false` |
| `production_enforce_hold_authorized` | `false` |
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

## Required Evidence Chains

The packet must prove both chains are current. Either chain missing means the
packet must use `request_proposal_changes` or
`reject_production_implementation`.

| Chain | Required Evidence |
|---|---|
| pre-policy-hold runtime safety | same-head smoke proves explicit opt-in, default-off behavior, redaction, fail-open, and no default `memory_search` mutation |
| policy-benefit quality | same-head or freshness-window live Mac eval proves expected positives are preserved and baseline false hits are removed |

These chains answer different questions. Runtime safety evidence does not prove
policy benefit. Policy-benefit evidence does not prove runtime safety.

## Required Evidence Fields

The approval packet must embed or reference:

| Evidence Field | Required |
|---|---|
| `repo_head` | exact current `HEAD` |
| `github_branch_head` | exact GitHub branch head |
| `worktree_clean` | `true` |
| `mcp_lifecycle_state` | `ready` |
| `mcp_readiness_warnings` | `0` |
| `daemon_http_healthy` | `true` |
| `palace_healthy` | `true` |
| `repeatable_smoke_status` | `passed` or explicitly `not_applicable_with_reason` |
| `trigger_recall_example_tests` | `passed` |
| `policy_benefit_fixture_status` | `passed` |
| `live_mac_check_corpus_status` | `passed` |
| `live_mac_policy_benefit_status` | `passed` |
| `full_live_corpus_expected_refs` | `30/30` |
| `full_live_corpus_ready` | `true` |
| `policy_benefit_positive_baseline_hits` | `all scoped positives` |
| `positive_cases_held` | `0` |
| `true_hits_lost_by_shadow_gate` | `0` |
| `accepted_order_drift` | `0` |
| `baseline_false_hits_after_gate` | `0` |
| `false_hits_removed_by_shadow_gate` | `> 0` |
| `contract_passed` | `true` |
| `ready_for_production_review` | `true` |
| `raw_payload_leak_check` | `true` |
| `held_bare_empty_arrays` | `0` |

The known CJK-only case `nexus_wuxing_math` must remain separated from the
baseline-findable policy-benefit contract unless a future tokenizer/indexing
proposal explicitly changes that boundary.

## Required Freshness Rules

The packet is invalid when any are true:

- the reviewed proposal commit is not the current branch head or is not named;
- the live Mac eval is older than the packet freshness window;
- thread `#120` has newer unresolved owner constraints after the cited decision;
- the worktree is dirty with unreviewed code changes;
- `policy_benefit_eval.v0` no longer reports `contract_passed=true`;
- default `memory_search` behavior/schema/order has changed;
- the candidate branch includes tokenizer, schema, index, reindex, semantic, or
  graph retrieval changes not separately approved.

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

This skeleton is intentionally non-approving until a future owner fills the
fields and sets a valid `owner_decision`.

```json
{
  "schema": "agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_approval.v0",
  "owner_decision": "request_proposal_changes",
  "owner_identity": "TBD",
  "forum_post_id": "TBD",
  "memory_key": "TBD",
  "proposal_design_commit": "c530023",
  "policy_benefit_review_packet_commit": "281b001",
  "policy_benefit_repair_commit": "7171e7d",
  "approved_implementation_branch": "TBD",
  "approved_mode": "pre_policy_hold_candidate",
  "approved_runtime_surface": "Niche/all-profile explicit opt-in only",
  "implementation_code_authorized": false,
  "runtime_enablement_authorized": false,
  "production_enforce_hold_authorized": false,
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
    "github_branch_head": "TBD",
    "worktree_clean": true,
    "mcp_lifecycle_state": "ready",
    "mcp_readiness_warnings": 0,
    "daemon_http_healthy": true,
    "palace_healthy": true,
    "repeatable_smoke_status": "TBD",
    "trigger_recall_example_tests": "passed",
    "policy_benefit_fixture_status": "passed",
    "live_mac_check_corpus_status": "passed",
    "live_mac_policy_benefit_status": "passed",
    "full_live_corpus_expected_refs": "30/30",
    "full_live_corpus_ready": true,
    "policy_benefit_positive_baseline_hits": "all scoped positives",
    "positive_cases_held": 0,
    "true_hits_lost_by_shadow_gate": 0,
    "accepted_order_drift": 0,
    "baseline_false_hits_after_gate": 0,
    "false_hits_removed_by_shadow_gate": ">0",
    "contract_passed": true,
    "ready_for_production_review": true,
    "raw_payload_leak_check": true,
    "held_bare_empty_arrays": 0
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
- proposal design commit exists and is docs-only;
- policy-benefit repair and review packet commits are named;
- approved implementation branch/worktree is isolated;
- runtime enablement remains false;
- production `enforce_hold` authorization remains false;
- default `memory_search` change remains false;
- non-Niche exposure remains false;
- write/reindex/retrieval side effects remain false;
- rollback names both disable env and binary revert;
- both evidence chains are current at the packet head;
- all zero-threshold policy-benefit metrics are zero;
- `false_hits_removed_by_shadow_gate` is greater than zero;
- packet does not include raw query, raw keys, content, or exact local scope
  outside hashed/redacted evidence.

## Next Gate

Allowed next:

- post this schema/checklist to thread `#120`;
- save it as an AB memory constraint;
- wait for an explicit owner packet before implementation code.

Still blocked:

- candidate code implementation;
- runtime enablement;
- default retrieval changes;
- deploy or GTE cutover tied to this policy.
