# Structured task context in session handoff

## Outcome and scope

The owner's 2026-10-27 request followed the concrete-code-task discussion:
retain the research conclusions in AB memory/board, then plan and implement
the next goal. This slice adds optional structured `task_context` to the
existing `session_handoff` MCP tool. It does not open the deferred work-memory
version check or UI tasks.

The trigger is a handoff whose 4,000-character transcript prefix omits a later
user correction. The new object independently carries the original request
and source, ordered user updates, current delivery, acceptance criteria,
delivered items, remaining gap, next action and return point. Missing source
references stay null. Original and current delivery can differ without the
tool inventing authorization. This borrows the continuity idea from OpenDuet;
it is an independent implementation, not copied upstream code.

## Implementation

- `crates/bridge/src/session_handoff.rs`: schema and strict shape, character,
  list and aggregate UTF-8 size validation. No normalization or truncation.
- `crates/bridge/src/mcp_tools.rs`: validate before store/git reads, then attach
  the exact context to the existing response. Omission retains legacy output.
- The response marks provenance `caller_supplied` and acceptance unverified,
  even when narrative status is `succeeded`. No writes or automatic forwarding.
- [Usage and limits](../operations/SESSION_HANDOFF_TASK_CONTEXT.md) and
  [goal review](../operations/GOAL_REVIEW.md) document the calling contract.

## Validation

Tests were added before production changes. Against the old implementation,
the four MCP tests produced **1 pass / 3 expected failures**: legacy output
passed; literal preservation, invalid-input rejection and preservation across
transcript clipping failed because the field was ignored. Build completed;
these were assertion failures, not compilation failures.

Candidate test command:

```sh
CARGO_TARGET_DIR=/Data/ab-main-rs-governance-target \
  cargo test -p ab-bridge --lib --no-default-features session_handoff -- --test-threads=1
```

Candidate result: **10 passed, 0 failed** (five existing handoff
regressions and five new MCP cases) covering goal changes, literal text,
unknown provenance, legacy shape, malformed inputs, Unicode boundaries,
array bounds and aggregate bytes. Local test log:
`/home/pallasting/.agent-bridge-secure/research/copilotkit-four-20261027/task-context-tests.log`.

## Follow-up boundary

Source tests are not installed-runtime or anti-drift effectiveness evidence.
No release binary was installed, MCP connection refreshed, remote pushed,
CI dispatched or child consumption verified in this slice. Live use requires
a binary containing this change and a refreshed MCP connection with the tool
available. Reopen on a concrete caller need or a failing boundary case;
do not automatically start the deferred features.

Tracking: memory `ab_task_context_code_plan_20261027`, design thread 115,
plan post 6361. The earlier workflow-only adoption is recorded separately in
[its report](2026-10-27-copilotkit-task-continuity.md).
