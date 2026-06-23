# Trigger Recall Approval Packet Validator

Date: 2026-06-23

Scope: implementation report for the read-only validator for
`agent_bridge.memory.trigger_recall.enforce_hold_approval_packet.v0`.

This slice does not implement `trigger_recall_opt_in_pre_policy_hold_simulation`,
does not implement production `enforce_hold`, does not change default
`memory_search`, does not deploy behavior, and does not write memory or graph
state.

## Verdict

`READ-ONLY-VALIDATOR-LANDED`.

The new validator consumes an approval packet and returns a redacted readiness
decision for only two allowed implementation modes:

- `audit_only`
- `pre_policy_hold`

It always returns:

- `may_implement_enforce_hold=false`
- `may_change_default_memory_search=false`

## Code Changes

Files changed:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`

New pure schema:

```text
agent_bridge.memory.trigger_recall.enforce_hold_approval_packet_validator.v0
```

New Niche MCP tool:

```text
trigger_recall_enforce_hold_approval_packet_validator
```

The tool is all-profile / Niche only. It stays out of standard eager profiles.

## Validation Boundary

The validator blocks unless all hard gates pass:

- exact approval packet schema;
- `read_only=true`;
- mode is `audit_only` or `pre_policy_hold`;
- implementation commit, reviewer, author, forum post id, memory key, and
  non-expired `expires_at` are present;
- exact local project scope and `scope_mode=local_only`;
- retrieval mode is `fts`;
- per-call opt-in and unchanged default `memory_search` are asserted;
- batch diagnostics status and regression anchor match;
- false-hit / lost-hit / positive-held metrics are zero;
- raw payload and bare-empty-held-result counters are zero;
- rollback names fail-open behavior.

The output never echoes the approval packet, scope path, raw query, raw key, or
content. Free-form packet references are represented as hashes or booleans.

## Side Effects

The implementation is pure/read-only:

- no store FTS call;
- no MCP `memory_search` call;
- no semantic or graph retrieval;
- no coactivation recording;
- no memory write;
- no graph-edge write;
- no default search schema or order change;
- no production retrieval-default change.

## Verification

Commands run from the isolated worktree
`/Data/CascadeProjects/agent-bridge-trigger-validator`:

```bash
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib approval_packet_validator -- --nocapture
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
CARGO_BUILD_JOBS=2 cargo check -p ab-bridge --lib
```

Results:

- approval-packet validator tests: 6 passed;
- trigger-recall opt-in tests: 24 passed;
- `cargo check -p ab-bridge --lib`: passed with existing warnings only.

## Boundary Still Closed

Still not authorized:

- merge/runtime use of `trigger_recall_opt_in_pre_policy_hold_simulation`;
- production `enforce_hold`;
- default `memory_search` behavior, schema, or ordering changes;
- hidden default-search parameters;
- held results as bare `[]`;
- coactivation or access traces for withheld hits;
- memory or graph writes;
- semantic or graph retrieval.

The next safe step is to use this validator to review any future Stage-2
approval packet before implementing or merging runtime hold simulation code.
