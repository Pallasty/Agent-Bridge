# Trigger Recall Pre-Policy Hold Simulation Implementation Proposal

Date: 2026-06-23

Scope: docs-only implementation proposal for the next trigger-recall opt-in
slice. This proposal does not implement runtime code, does not authorize
production `enforce_hold`, does not change default `memory_search`, does not
deploy, and does not write memory or graph edges.

## Verdict

`PROPOSAL-ONLY-IMPLEMENTATION-NO-GO`.

The next code slice, if later approved by an exact approval packet, should be:

```text
trigger_recall_opt_in_pre_policy_hold_simulation
```

This should be a separate Niche MCP surface. It must not be a parameter on
default `memory_search`.

## Recalibrated Target

Project design goal:

- reduce false-positive trigger recall retrieval behavior through explicit,
  reviewable, opt-in gates;
- preserve the existing `memory_search` public contract until a separate
  production authorization exists;
- make held-query behavior visible as a structured status object, not an empty
  search result;
- avoid coactivation/access evidence for hits that are withheld by policy.

Current implementation:

| Surface | State | Store Search |
|---|---|---:|
| `trigger_recall_opt_in_status` | landed | no |
| `trigger_recall_opt_in_runtime_transition_gate` | landed | no |
| `trigger_recall_opt_in_gated_baseline_trial` | landed | yes, after transition gate |
| `trigger_recall_opt_in_gated_batch_diagnostics` | landed | no |
| `trigger_recall_opt_in_pre_policy_hold_simulation` | missing | proposed |
| production `enforce_hold` | missing and still NO-GO | not authorized |

Session goal:

- close the gap between schema review and code authorization by naming exact
  files, functions, tests, env gates, and rollback behavior for the next
  proposal-only slice.

## Implementation Boundary

Do not modify:

- default `memory_search` schema;
- default `memory_search` behavior;
- tokenizer, schema, indexing, or reindex logic;
- semantic retrieval;
- graph retrieval;
- coactivation behavior;
- memory or graph write paths.

Add only a new opt-in simulation surface and pure payload helpers.

## Proposed Files

Expected code files for a future implementation commit:

| File | Change |
|---|---|
| `crates/bridge/src/trigger_recall_opt_in.rs` | add schema constant, env constants, option structs, pure simulation payload builder, tests |
| `crates/bridge/src/mcp_tools.rs` | add Niche MCP tool wrapper, schema, execution wiring, registry tests |

Expected report file for that future implementation:

```text
docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-simulation.md
```

No store crate changes are proposed for the first implementation. Reuse
existing store FTS through the same baseline path used by the gated baseline
trial.

## Proposed Constants

Add to `crates/bridge/src/trigger_recall_opt_in.rs`:

```rust
pub const TRIGGER_RECALL_PRE_POLICY_HOLD_SIMULATION_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.pre_policy_hold_simulation.v0";
pub const TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN_ENV: &str =
    "AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN";
pub const TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE_ENV: &str =
    "AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE";
```

Keep existing `AB_TRIGGER_RECALL_OPT_IN` gates unchanged.

## Proposed Pure Types

Add a pure option payload near the existing trigger-recall types:

```rust
pub struct TriggerRecallPrePolicyHoldSimulationOptions {
    pub approval_packet: Value,
    pub query: String,
    pub tags_count: usize,
    pub limit: u64,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub scope: Option<String>,
    pub scope_mode: String,
    pub include_baseline_counts: bool,
    pub runtime_enabled: bool,
    pub operator_disabled: bool,
    pub raw_payload_fields_present: bool,
    pub baseline_search_called: bool,
    pub baseline_hits: Option<Vec<TriggerRecallOptInGatedBaselineTrialHit>>,
    pub baseline_search_error: Option<String>,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}
```

Reuse:

- `trigger_recall_baseline_acceptance_reject_reason`;
- `trigger_recall_value_contains_raw`;
- `exact_local_project_scope`;
- `baseline_order_hash`;
- `redacted_hit_summary`;
- `TriggerRecallOptInGatedBaselineTrialHit`.

## Approval Packet Validation

The future helper should validate the schema from
`2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`.

Required approval packet values:

| Field | Required |
|---|---|
| `schema` | `agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0` |
| `packet_status` | `approved_for_pre_policy_hold_simulation` |
| `approved_mode` | `pre_policy_hold_simulation` |
| `implementation_commit` | exact current implementation commit |
| `regression_anchor` | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| `default_memory_search_unchanged` | true |
| `raw_query_included` | false |
| `raw_keys_included` | false |
| `content_included` | false |
| `rollback` | non-empty |

If approval is missing or malformed, return `blocked_to_baseline`. The wrapper
may call baseline FTS to preserve baseline behavior, but must report the
blockers and must not claim policy hold was applied.

## Proposed MCP Surface

Add a Niche/all-profile tool:

```text
trigger_recall_opt_in_pre_policy_hold_simulation
```

Required input:

- `approval_packet`;
- `query`;
- `per_call_opt_in`.

Optional input:

- `tags_any`;
- `limit`;
- `mode`;
- `scope`;
- `scope_mode`;
- `include_baseline_counts`;
- `operator_disabled`;
- `attempt_id`;
- `commit`.

Forbidden input fields:

- raw keys;
- candidate keys;
- baseline keys;
- content;
- raw content;
- mutate/write flags.

The tool must stay out of the default Codex essential profile unless a later
tool-surface review explicitly changes that.

## Execution Semantics

The future tool should use this order:

1. Parse and validate the approval packet.
2. Validate runtime env, operator disable, per-call opt-in, `mode=fts`, exact
   local project scope, and redaction boundary.
3. Compute query-intent reject reason before baseline search.
4. If the query is held and `include_baseline_counts=false`, return a held
   packet without store search.
5. If the query is held and `include_baseline_counts=true`, call store FTS only
   for count/order-hash audit, return no visible hits, and mark
   `baseline_count_status=count_audit_requested`.
6. If the query is accepted, call baseline store FTS, preserve baseline order,
   and return accepted visible hit summaries.
7. If gates are blocked, fail open to baseline behavior and report
   `blocked_to_baseline`.

The tool must not call the MCP `memory_search` tool. It may call the store FTS
path directly, as the gated baseline trial already does.

## Response Contract

Required status values:

| Status | Meaning |
|---|---|
| `returned_accepted` | approved simulation, query allowed, baseline hits visible |
| `held_by_query_intent` | approved simulation, query held before store search by default |
| `would_hold` | optional audit-only mode, not the first implementation target |
| `blocked_to_baseline` | gate/approval missing, baseline behavior returned |
| `operator_disabled` | disable switch active, baseline behavior returned |
| `baseline_search_error` | accepted or fail-open baseline lookup failed |

Held response requirements:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold_simulation.v0",
  "mode": "pre_policy_hold_simulation",
  "status": "held_by_query_intent",
  "default_memory_search_unchanged": true,
  "changes_this_opt_in_call": true,
  "visible_hits": [],
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "baseline": {
    "store_search_called": false,
    "memory_search_mcp_called": false,
    "baseline_count_status": "not_requested_pre_policy_hold",
    "baseline_candidate_count": null
  }
}
```

## Side-Effect Contract

Required for held queries when count audit is not requested:

| Side Effect | Required |
|---|---|
| store search | false |
| MCP `memory_search` | false |
| coactivation trace | false |
| access-count bump | false |
| memory write | false |
| graph write | false |
| semantic retrieval | false |
| graph retrieval | false |

For accepted queries and fail-open baseline behavior, any store lookup must
preserve the existing gated-trial side-effect boundary: no coactivation, no
memory/graph write, no default search schema/order change.

## Tests Required

Add or preserve tests in `crates/bridge/src/trigger_recall_opt_in.rs`:

| Test | Assertion |
|---|---|
| `pre_policy_hold_blocks_before_store_search_by_default` | held query returns object status and `store_search_called=false` |
| `pre_policy_hold_count_audit_calls_store_without_visible_hits` | count audit records count/hash but returns no visible hits |
| `pre_policy_hold_accepts_and_preserves_baseline_order` | accepted query returns baseline summaries and order hash |
| `pre_policy_hold_missing_approval_fails_open` | malformed approval reports `blocked_to_baseline` |
| `pre_policy_hold_operator_disable_fails_open` | disable env reports `operator_disabled` |
| `pre_policy_hold_rejects_raw_payload_without_echoing` | raw query/key/content not echoed |
| `pre_policy_hold_non_fts_blocks` | hybrid/semantic rejected |
| `pre_policy_hold_non_local_scope_blocks` | non-exact local scope rejected |

Add or preserve tests in `crates/bridge/src/mcp_tools.rs`:

| Test | Assertion |
|---|---|
| schema registration | tool exists in all/Niche profile, not essential profile |
| schema input | approval packet, query, per-call opt-in required |
| forbidden fields | no raw keys/content/mutate fields |
| blocked before search | missing approval does not claim hold |
| held before search | approved held query does not call store FTS |
| accepted path | approved accepted query calls store FTS and redacts keys/content |

## Verification Commands

Required before any implementation approval packet:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
cargo check -p ab-bridge --lib
git diff --check
```

Do not run unbounded full-file `rustfmt --check` over
`crates/bridge/src/mcp_tools.rs` while the known large formatter diff remains.

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

## Rollback

The future implementation must support:

```text
AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE=1
```

When set:

- return baseline behavior through the simulation surface;
- report `operator_disabled`;
- do not apply held-query behavior;
- do not change default `memory_search`;
- do not write memory or graph state.

## Non-Goals

This proposal does not authorize:

- implementing code now;
- production `enforce_hold`;
- default `memory_search` parameters;
- default retrieval behavior changes;
- hybrid or semantic mode;
- tokenizer/schema/indexing/reindex changes;
- graph/semantic expansion;
- coactivation/access traces for withheld hits;
- memory writes;
- graph-edge writes.

## Next Gate

Closed by
`docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-implementation-proposal-review.md`,
`docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-stage1-candidate-authorization.md`,
and
`docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-stage2-acceptance-checklist.md`.

Current safe actions:

- use the Stage-1 authorized `/Users/...` worktree if operating on that host;
- or write a Stage-1 amendment naming an exact Aio2 `/Data/...` worktree before
  producing candidate code in this environment;
- after an exact candidate commit exists, run the Stage-2 checklist and require
  a separate Stage-2 approval packet naming that commit before merge/runtime
  use.

Until a checkout-specific Stage-1 authorization applies, candidate work in that
checkout remains blocked. Until a Stage-2 exact-commit packet exists,
merge/runtime work remains `IMPLEMENTATION-NO-GO`.
