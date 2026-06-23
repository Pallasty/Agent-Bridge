# Trigger Recall Enforce Hold Approval Packet Schema

Date: 2026-06-23

Scope: approval-packet schema and review contract only. This document does not
implement `enforce_hold`, does not change default `memory_search`, does not
register a runtime MCP tool, does not deploy behavior, and does not write
memory or graph edges.

## Verdict

`SCHEMA-DESIGN-ONLY`.

The next admissible implementation slice may be approved only for
`audit_only` or `pre_policy_hold` simulation. Production `enforce_hold` remains
`IMPLEMENTATION-NO-GO`.

## Packet Schema

Schema id:

```text
agent_bridge.memory.trigger_recall.enforce_hold_approval_packet.v0
```

Minimum packet shape:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.enforce_hold_approval_packet.v0",
  "generated_at": "2026-06-23T00:00:00Z",
  "read_only": true,
  "approval_packet": true,
  "approval_kind": "implementation_slice_approval",
  "approved_mode": "pre_policy_hold",
  "implementation_commit": "sha",
  "reviewer": "codex-or-human-reviewer",
  "author": "implementation-owner",
  "forum_post_id": "3983",
  "memory_key": "trigger_recall_gated_batch_installed_review_20260623",
  "expires_at": "2026-06-30T00:00:00Z",
  "scope": "project:/Users/pallasting/Projects/agent-bridge",
  "scope_mode": "local_only",
  "mode": "fts",
  "per_call_opt_in_required": true,
  "default_memory_search_unchanged": true,
  "runtime_env": {
    "enable": "AB_TRIGGER_RECALL_ENFORCE_HOLD_OPT_IN=1",
    "disable": "AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1"
  },
  "evidence": {
    "batch_diagnostics_status": "ready_for_enforce_hold_review_packet",
    "batch_diagnostics_summary": {
      "packet_count": 3,
      "returned_accepted_count": 1,
      "held_by_query_intent_count": 1,
      "transition_gate_blocked_count": 1,
      "raw_payload_blocked_count": 0,
      "expectation_mismatch_count": 0,
      "batch_tool_calls_memory_search_count": 0
    },
    "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623",
    "baseline_false_hits_after_shadow_gate": 0,
    "true_hits_lost_by_shadow_gate": 0,
    "positive_cases_held": 0,
    "raw_payload_leaks": 0,
    "held_bare_empty_arrays": 0
  },
  "required_commands": [
    "cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture",
    "cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture",
    "cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit",
    "cargo check -p ab-bridge --lib",
    "git diff --check"
  ],
  "rollback": {
    "disable_env": "AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1",
    "expected_behavior": "fail_open_to_baseline"
  },
  "decision": {
    "may_implement_audit_only": true,
    "may_implement_pre_policy_hold": true,
    "may_implement_enforce_hold": false,
    "may_change_default_memory_search": false
  }
}
```

## Allowed Modes

| Approved mode | Meaning | Store search for held queries | Visible behavior |
|---|---|---|---|
| `audit_only` | reports `would_hold` without suppressing visible baseline hits | baseline/audit path allowed | baseline hits stay visible |
| `pre_policy_hold` | production-shaped hold simulation with explicit held packet | no store search unless `include_baseline_counts=true` | held packet, not bare `[]` |

`approved_mode=enforce_hold` is invalid for this packet version. A later
packet version may introduce production `enforce_hold`, but only after a
separate board decision and implementation review.

## Validation Contract

A future approval-packet validator should return one of:

- `approval_packet_ready`
- `blocked_schema_mismatch`
- `blocked_missing_reviewer`
- `blocked_missing_author`
- `blocked_missing_implementation_commit`
- `blocked_missing_forum_post`
- `blocked_missing_memory_key`
- `blocked_expired_packet`
- `blocked_mode_not_allowed`
- `blocked_scope_not_exact_local_project`
- `blocked_scope_mode_not_local_only`
- `blocked_retrieval_mode_not_fts`
- `blocked_default_memory_search_change`
- `blocked_batch_diagnostics_not_ready`
- `blocked_regression_anchor_mismatch`
- `blocked_metric_threshold_failed`
- `blocked_raw_payload_or_empty_hold_leak`
- `blocked_rollback_missing`

Any blocked status must fail open to baseline behavior. It must not partially
enable visible hold behavior.

## Hard Gates

All gates are required before a future implementation slice can proceed:

| Gate | Required value |
|---|---|
| schema | `agent_bridge.memory.trigger_recall.enforce_hold_approval_packet.v0` |
| `read_only` | `true` |
| approved mode | `audit_only` or `pre_policy_hold` |
| implementation commit | exact non-empty commit hash |
| reviewer / author | non-empty |
| forum post id | non-empty and board-visible |
| memory key | non-empty |
| scope | exact `project:/...` local project scope |
| scope mode | `local_only` |
| retrieval mode | `fts` |
| per-call opt-in | required |
| default memory search | unchanged |
| batch diagnostics | `ready_for_enforce_hold_review_packet` |
| raw payload leaks | `0` |
| held bare empty arrays | `0` |
| positive cases held | `0` |
| true hits lost by shadow gate | `0` |
| baseline false hits after shadow gate | `0` |
| rollback | disable env and fail-open behavior named |

## Review Rules

1. Approval cannot be inferred from metrics alone.
2. Approval cannot be inferred from a forum post unless the post names the exact
   `approved_mode` and `implementation_commit`.
3. Approval cannot be inferred from a memory note unless the same evidence is
   board-visible.
4. A stale packet is invalid even if the metrics still look good.
5. A packet approving `audit_only` does not authorize `pre_policy_hold`.
6. A packet approving `pre_policy_hold` does not authorize production
   `enforce_hold`.
7. Default `memory_search` must remain a bare hit-list search.

## Implementation Boundary

The first code slice after this schema, if approved, should be a pure validator
or packet-review helper. It may parse a packet and emit a readiness decision,
but it must not:

- alter retrieval results;
- call store FTS except for explicit audit-count paths;
- record coactivation for withheld hits;
- write memories;
- write graph edges;
- register a default-profile MCP tool;
- expose raw query, key, content, scope path, or visible hit bodies.

If implemented as an MCP tool, it should be `Tier::Niche` and available only
under `AGENT_BRIDGE_TOOL_PROFILE=all` until usage evidence justifies promotion.

## Next Safe Slice

Implement a read-only approval-packet validator for
`agent_bridge.memory.trigger_recall.enforce_hold_approval_packet.v0`.

The validator should consume a packet, return a redacted readiness result, and
force:

```json
{
  "may_implement_audit_only": false,
  "may_implement_pre_policy_hold": false,
  "may_implement_enforce_hold": false,
  "may_change_default_memory_search": false
}
```

unless every hard gate passes and the requested mode is exactly
`audit_only` or `pre_policy_hold`.
