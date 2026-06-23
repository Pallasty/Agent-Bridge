# Trigger Recall Pre-Policy Hold Approval Packet Schema

Date: 2026-06-23

Scope: approval-packet schema and review requirements for a future
`pre_policy_hold` simulation slice. This document does not implement runtime
behavior, does not authorize `enforce_hold`, does not change default
`memory_search`, does not register a new MCP tool, does not deploy, and does
not write memory or graph edges.

## Verdict

`SCHEMA-ONLY-IMPLEMENTATION-NO-GO`.

The next implementable shape, if later approved, should be
`pre_policy_hold_simulation`, not production `enforce_hold`.

The purpose of this packet schema is to make future approval unambiguous:

- an approval must name the exact mode;
- an approval must name the exact implementation commit;
- held queries must return an explicit object response, never a bare empty
  result;
- default `memory_search` must remain unchanged;
- rejected query intent must run before store search unless the caller
  explicitly requests count-audit evidence.

## Status Verified Before This Design

Current local status at the start of this schema pass:

| Check | Result |
|---|---|
| branch | `master` |
| HEAD | `05c3e7e docs(memory): review trigger gated batch diagnostics` |
| remote sync | `HEAD == origin/master` |
| worktree | clean |
| MCP lifecycle | ready |
| daemon-http health | ready |
| Palace health and graph | ready |
| `agent-bridge.real doctor --json` | `ok=true`, `fails=0`, `warns=0` |
| kernel OOM since rustfmt lesson | no new OOM/Cursor/rustfmt hits observed |

Verification rerun on current HEAD:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo check -p ab-bridge --lib
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
git diff --check
```

Observed results:

| Check | Result |
|---|---|
| trigger opt-in lib tests | 21 passed |
| lib check | passed with existing warnings only |
| active rows | 458 |
| trigger rows | 30 |
| projected rows | 29 |
| baseline/shadow R@10 | 0.857 |
| baseline/shadow MRR | 0.786 |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits before shadow gate | 21 |
| baseline false hits after shadow gate | 0 |
| diff check | clean |

## Packet Schema

A future approval packet should use this logical schema:

```text
agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0
```

Required top-level fields:

| Field | Requirement |
|---|---|
| `schema` | exact schema above |
| `packet_status` | `proposal`, `approved_for_audit_only`, `approved_for_pre_policy_hold_simulation`, or `rejected` |
| `approved_mode` | `audit_only` or `pre_policy_hold_simulation`; never implicit |
| `author` | non-empty stable author id |
| `reviewer` | non-empty reviewer id distinct from author when possible |
| `forum_thread_id` | board-visible thread id |
| `forum_post_id` | post id containing the decision |
| `implementation_commit` | exact commit to review; required before implementation |
| `base_commit` | commit used for verification |
| `expires_at` | freshness limit or explicit `none_with_reason` |
| `regression_anchor` | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| `default_memory_search_unchanged` | must be true |
| `raw_query_included` | must be false |
| `raw_keys_included` | must be false |
| `content_included` | must be false |
| `rollback` | operator disable path and revert plan |

The packet must be rejected if the mode or implementation commit is omitted.

## Approved Mode Vocabulary

Only these modes are valid for the next approval step:

| Mode | Meaning | Store Search On Held Query | Visible Hold |
|---|---|---:|---:|
| `audit_only` | report `would_hold` but return baseline behavior | allowed for evidence | no |
| `pre_policy_hold_simulation` | return production-shaped held packet without production authority | no by default | only in the explicit opt-in simulation surface |

Invalid for this schema:

| Mode | Reason |
|---|---|
| `enforce_hold` | requires a separate post-simulation approval |
| `hybrid` | baseline acceptance evidence is `fts` only |
| `semantic` | semantic retrieval is out of scope |
| default `memory_search` parameter | hidden behavior change is disallowed |

## Required Future Response Contract

The implementation under review must return an object response.

Minimum held response:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold_simulation.v0",
  "mode": "pre_policy_hold_simulation",
  "status": "held_by_query_intent",
  "default_memory_search_unchanged": true,
  "changes_this_opt_in_call": true,
  "hits": [],
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "baseline": {
    "store_search_called": false,
    "memory_search_mcp_called": false,
    "baseline_count_status": "not_requested_pre_policy_hold",
    "baseline_candidate_count": null
  },
  "audit": {
    "query_hash": "sha256:...",
    "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623",
    "raw_query_included": false,
    "raw_keys_included": false,
    "content_included": false
  }
}
```

Minimum accepted response:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold_simulation.v0",
  "mode": "pre_policy_hold_simulation",
  "status": "returned_accepted",
  "default_memory_search_unchanged": true,
  "changes_this_opt_in_call": false,
  "hits": [],
  "baseline": {
    "store_search_called": true,
    "memory_search_mcp_called": false,
    "baseline_order_preserved": true
  }
}
```

The example leaves `hits` empty only as a redacted schema example. An accepted
trial may return the same visible hit shape already used by the gated baseline
trial, but it must not expose raw keys or content in audit fields.

## Pre-Policy Gate Requirements

Rejected query intent must short-circuit before baseline store search by
default.

Required held-query side effects:

| Side Effect | Required |
|---|---|
| store FTS search | false by default |
| MCP `memory_search` call | false |
| coactivation trace for withheld hits | false |
| access-count bump for withheld hits | false |
| memory write | false |
| graph-edge write | false |
| semantic or graph retrieval | false |

The only exception is an explicit count-audit mode. If a future packet approves
count-audit evidence, it must set:

```text
include_baseline_counts=true
baseline_count_status=count_audit_requested
```

and still must not treat the count-audit search as normal production behavior.

## Authorization Gates

All gates must pass before a future implementation can be approved for
`pre_policy_hold_simulation`:

| Gate | Required State |
|---|---|
| approval packet | present, schema-valid, board-visible |
| approved mode | exactly `pre_policy_hold_simulation` |
| implementation commit | exact commit named |
| operator env | proposed `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1` |
| operator disable | proposed `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE` absent/false |
| per-call opt-in | true |
| mode | `fts` |
| scope | exact local project scope |
| scope mode | `local_only` |
| regression anchor | current and passing |
| batch diagnostics | `ready_for_enforce_hold_review_packet` evidence present |
| response status | held is distinct from empty search |
| raw fields | no raw query, keys, content, or scope path in output |

If any gate fails, the wrapper must report `blocked_to_baseline` or
`operator_disabled` and fail open to baseline behavior.

## Required Tests For A Future Implementation

The implementation commit named by a future approval packet must add or preserve
tests proving:

| Case | Requirement |
|---|---|
| held query | returns `held_by_query_intent` object, not `[]` |
| held query default | does not call store search |
| held query count audit | calls store search only when counts are explicitly requested |
| accepted query | calls baseline FTS and preserves baseline order |
| missing per-call opt-in | fails open to baseline behavior |
| operator disable | fails open to baseline behavior |
| non-`fts` mode | blocks |
| non-local scope | blocks |
| raw payload marker | rejected and not echoed |
| default `memory_search` | unchanged schema and behavior |

## Required Verification Commands

Run these before posting an implementation approval packet:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
cargo check -p ab-bridge --lib
git diff --check
```

Do not run unbounded full-file `rustfmt --check` over
`crates/bridge/src/mcp_tools.rs` while it still carries the known large diff.
If a formatter diagnostic is needed, use targeted formatting or a memory cap.

Required thresholds:

| Metric | Required |
|---|---:|
| trigger opt-in tests | all pass |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits after shadow gate | 0 |
| accepted order drift | 0 |
| raw query/key/content leaks | 0 |
| held responses as bare arrays | 0 |

## Rollback And Disable

Any future implementation must include a single operator kill switch:

```text
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE=1
```

When set, the wrapper must:

- return baseline behavior;
- report `operator_disabled`;
- not enforce or simulate a visible hold;
- not alter default `memory_search`;
- not write memory or graph state.

## Review Decision Template

A future forum/review post should include this block:

```text
Decision: APPROVED-FOR-PRE-POLICY-HOLD-SIMULATION
Mode: pre_policy_hold_simulation
Implementation commit: <sha>
Approval packet schema: agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0
Regression anchor: aio2_trigger_recall_baseline_acceptance_shadow_20260623
Default memory_search unchanged: yes
Held response is object, not []: yes
Operator disable: AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE=1
Expires: <date or none_with_reason>
```

Without this exact decision shape, implementation remains `NO-GO`.

## Next Gate

The next safe action is a docs-only review of this schema, or an implementation
proposal that names exact files and tests while still stopping at
`pre_policy_hold_simulation`.

Do not implement production `enforce_hold`, and do not modify default
`memory_search`.
