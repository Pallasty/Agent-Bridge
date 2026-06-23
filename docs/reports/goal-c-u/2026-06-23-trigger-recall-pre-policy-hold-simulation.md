# Trigger Recall Pre-Policy Hold Simulation Candidate

Date: 2026-06-23

Scope: candidate-only implementation of
`trigger_recall_opt_in_pre_policy_hold_simulation` in the isolated worktree
`/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate`.

This report is not a merge approval, deploy approval, or production
`enforce_hold` approval.

## Candidate Boundary

The candidate adds one opt-in Niche MCP surface:

```text
trigger_recall_opt_in_pre_policy_hold_simulation
```

It preserves these boundaries:

- default `memory_search` schema and behavior are unchanged;
- held queries return a structured object status, not a bare `[]`;
- held queries do not call store FTS unless `include_baseline_counts=true`;
- count-audit mode calls store FTS only for redacted count/order-hash evidence;
- accepted and fail-open paths may call store FTS directly but never call the
  MCP `memory_search` tool;
- raw query, memory keys, and content are not echoed;
- coactivation, access-count, memory-write, and graph-write paths are not used;
- semantic and graph retrieval are not used;
- the tool is registered as `Tier::Niche` and remains outside the Codex
  essential surface.

## Runtime Gates

The simulation requires:

- `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1`;
- no `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE`;
- `per_call_opt_in=true`;
- `mode=fts`;
- exact local `project:/abs/path` scope with `scope_mode=local_only`;
- an approval packet with schema
  `agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0`;
- approval packet `implementation_commit` matching the caller supplied
  `commit`.

Blocked or disabled gates fail open to baseline behavior through the simulation
surface and report `blocked_to_baseline` or `operator_disabled`.

## Verification

Current candidate verification:

| Command | Result |
|---|---|
| `cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture` | passed, 33 tests |
| `cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture` | passed, 27 tests |
| `cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit` | blocked on local corpus: missing expected key `lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620` |
| `cargo check -p ab-bridge --lib` | passed, existing warnings only |
| `git diff --check` | passed |

The blocked audit command exited with:

```text
Error: "aio2_lswr_g21_g22_apply_writer expected key missing: lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620"
```

Local memory verification also returned `null` for that exact key, so this is
recorded as a local aio2-corpus availability blocker rather than a candidate
code failure.

## Stage-2 Requirement

This candidate remains non-authorizing. A Stage-2 packet must name the exact
candidate commit before merge, deploy, or runtime simulation outside this
isolated branch.
