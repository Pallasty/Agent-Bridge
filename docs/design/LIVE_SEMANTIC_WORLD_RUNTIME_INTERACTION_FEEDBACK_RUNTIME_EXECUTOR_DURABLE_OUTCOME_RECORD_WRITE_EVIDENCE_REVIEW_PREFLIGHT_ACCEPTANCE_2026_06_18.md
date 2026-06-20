# Acceptance — Durable Outcome Record Write-Evidence Review Preflight

Date: 2026-06-18

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight -- --nocapture
```

Expected:

- missing review decision blocks with
  `explicit_durable_outcome_record_write_evidence_review_decision_required`;
- explicit scoped review decision returns
  `ready_for_world_verdict_rewrite_gate`;
- bad review decision blocks on kind, decision, source verdict, confirmation,
  readback, digest, idempotency, permission, and scope errors;
- wrong source input blocks with
  `runtime_executor_durable_outcome_record_write_evidence_preflight_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_smoke -- --format json --assert-blocked-without-durable-outcome-record-write-evidence-review --assert-read-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_smoke -- --with-durable-outcome-record-write-evidence-review --format json --assert-ready-for-world-verdict-rewrite-gate --assert-read-only
```

Expected ready fields:

- `durable_outcome_record_write_evidence_review_preflight_verdict=ready_for_world_verdict_rewrite_gate`;
- `next_allowed_gate=world_verdict_rewrite_gate`;
- `ready_for_world_verdict_rewrite_gate=true`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `world_verdict_rewrite_allowed=false`;
- `world_verdict_rewrite_performed_by_this_tool=false`.

## 2. Boundary

This accepted G16 preflight can recognize a scoped external review decision over
durable outcome record write evidence. It cannot perform durable writes, ingest
#94 outcomes, write memory, or rewrite the source world verdict.

The critical distinction is:

- `decision=approved_for_world_verdict_rewrite_gate`: review permits entering a
  later explicit gate;
- `ready_for_world_verdict_rewrite_gate=true`: the next gate may consume this
  review;
- `world_verdict_rewrite_allowed=false`: this preflight still cannot rewrite;
- `world_verdict_rewrite_performed_by_this_tool=false`: no verdict changed here.

## 3. Next Slice

The next safe slice is G17, the explicit world-verdict rewrite gate. It must
require its own rewrite decision, must not infer verdict rewrite solely from
durable write evidence or write-evidence review, and must keep the resulting
`verified` verdict package output-only until a later ingestion gate consumes it.
