# Trigger Recall Slice 1 Post-Implementation Review

Date: 2026-06-23

Base: `ef089bd` (`docs(memory): reconcile trigger opt-in review`)

Scope: post-implementation review and next-slice decision only. No runtime
implementation, no MCP surface change, no store search call, no memory writes,
no graph writes, no default `memory_search` change, and no deploy behavior
change.

## Verdict

`SLICE-1-POST-IMPLEMENTATION-REVIEW-PASS`.

`036ea17` satisfies the Slice 1 boundary from the production opt-in review:

- `trigger_recall_opt_in_status` exists as a read-only status surface.
- `trigger_recall_opt_in_runtime_transition_gate` exists as a read-only
  transition gate.
- The transition gate can allow only the later
  `trigger_recall_opt_in_gated_baseline_trial` surface.
- It does not authorize `enforce_hold`.
- It does not call `memory_search`.
- It does not expose raw query, raw keys, memory content, or the consumed status
  packet.
- It keeps default `memory_search` behavior unchanged.

## Transition Gate Artifact Shape Reviewed

The allowed transition gate shape is constrained to:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.opt_in_runtime_transition_gate.v0",
  "read_only": true,
  "runtime_transition_gate": true,
  "status": "transition_allowed",
  "transition": {
    "transition_allowed": true,
    "may_call_gated_baseline_trial": true,
    "may_enforce_hold": false,
    "next_allowed_surface": "trigger_recall_opt_in_gated_baseline_trial",
    "default_memory_search_unchanged": true
  },
  "side_effects": {
    "calls_memory_search": false,
    "records_coactivation": false,
    "writes_memory": false,
    "writes_graph_edges": false,
    "changes_memory_search_order": false,
    "changes_default_memory_search_schema": false
  }
}
```

Required blockers are present for malformed status packets, raw payload fields,
non-`fts` mode, missing per-call opt-in, missing exact local scope, runtime
disable, operator disable, and regression-anchor mismatch.

## Verification

Commands replayed on this base:

- `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture`
  - 7 passed.
- `cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture`
  - 27 passed.
- `cargo check -p ab-bridge --examples`
  - Passed with existing warnings only.
- `git diff --check`
  - Passed.

## Slice 2 Decision

`APPROVED-FOR-SLICE-2-SINGLE-CALL-IMPLEMENTATION`.

The next implementation may add `trigger_recall_opt_in_gated_baseline_trial`,
but only with these constraints:

- separate Niche/diagnostic MCP surface, not a `memory_search` parameter;
- requires a valid transition gate packet from Slice 1;
- requires `mode=fts`, `per_call_opt_in=true`, exact local project scope, and
  runtime opt-in;
- blocked or malformed gates must not call store search;
- allowed single calls may call store baseline FTS directly for this opt-in
  trial;
- the tool must not call the MCP `memory_search` tool;
- the tool must not record coactivation;
- output must be redacted by default: query hash yes, raw query no, raw keys no,
  memory content no, scope path no;
- accepted calls may return redacted hit summaries;
- rejected calls must return explicit `held_by_query_intent`, not a bare empty
  search result;
- `enforce_hold` remains `NO-GO`;
- default `memory_search` remains unchanged.

## Next Gate After Slice 2

After the single-call gated trial exists, run a redacted batch diagnostic over
the Aio2 positive and negative trigger controls. That later report should
compare:

- default baseline FTS;
- gated accepted calls;
- gated held calls;
- eval-only `union+cont`.

No production visible hold behavior should be considered until that batch
diagnostic and a separate review pass.
