# Acceptance — World-Verdict Rewrite Gate Preflight

Date: 2026-06-20

Status: IMPLEMENTED_G17_WORLD_VERDICT_REWRITE_GATE_PREFLIGHT_ONLY

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight -- --nocapture
```

Expected:

- missing gate decision blocks with
  `explicit_world_verdict_rewrite_gate_decision_required`;
- explicit scoped gate decision returns
  `ready_for_world_verdict_rewrite_execution`;
- bad gate decision blocks on kind, decision, source verdict, target verdict,
  confirmation, permission, and scope errors;
- wrong source input blocks with
  `runtime_executor_durable_outcome_record_write_evidence_review_preflight_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight_smoke -- --format json --assert-blocked-without-world-verdict-rewrite-gate-decision --assert-read-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight_smoke -- --with-world-verdict-rewrite-gate-decision --format json --assert-ready-for-world-verdict-rewrite-execution --assert-read-only
```

Expected ready fields:

- `world_verdict_rewrite_gate_preflight_verdict=ready_for_world_verdict_rewrite_execution`;
- `next_allowed_gate=world_verdict_rewrite_execution`;
- `ready_for_world_verdict_rewrite_execution=true`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `world_verdict_rewrite_allowed=false`;
- `world_verdict_rewrite_performed_by_this_tool=false`.

## 2. Boundary

This accepted G17 preflight can recognize a scoped external gate decision that
authorizes a later world-verdict rewrite execution. It cannot perform the
rewrite, write durable records, ingest #94 outcomes, write memory, or register
MCP tools.

The critical distinction is:

- `decision=approved_for_world_verdict_rewrite_execution`: the gate permits
  entering a later execution step;
- `ready_for_world_verdict_rewrite_execution=true`: the next execution preflight
  may consume this gate;
- `world_verdict_rewrite_allowed=false`: this preflight still cannot rewrite;
- `world_verdict_rewrite_performed_by_this_tool=false`: no verdict changed here.

## 3. Next Slice

The next safe slice is explicit world-verdict rewrite execution preflight. It
must require the accepted G17 gate output and keep the final mutation surface
separate and auditable.
