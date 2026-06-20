# Acceptance — Runtime Executor Verified Outcome Ingestion Apply Gate

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate -- --nocapture
```

Expected:

- missing apply decision blocks with
  `explicit_verified_outcome_ingestion_apply_decision_required`;
- explicit scoped apply decision returns
  `ready_for_verified_outcome_ingestion_writer`;
- bad apply decision blocks on kind, decision, source verdict, verified
  verdict, G20 review, package confirmations, attestation, lineage, digest,
  idempotency, permission, boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_execution_commit_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-apply-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_smoke -- --with-verified-outcome-ingestion-apply-decision --format json --assert-ready-for-verified-outcome-ingestion-writer --assert-output-only
```

Expected ready fields:

- `verified_outcome_ingestion_apply_verdict=ready_for_verified_outcome_ingestion_writer`;
- `next_allowed_gate=verified_outcome_ingestion_writer`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_writer=true`;
- `verified_outcome_ingestion_apply_gate_output_only=true`;
- `verified_outcome_ingestion_writer_allowed_after_gate=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G21 apply gate can emit a bounded writer-ready package from a scoped G20
package plus explicit apply decision. It cannot persist the verdict, write a
durable outcome record, ingest #94 outcomes, write memory, or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_writer`: explicit decision
  authorizes package emission for the next writer slice;
- `verified_outcome_ingestion_apply_verdict=ready_for_verified_outcome_ingestion_writer`:
  the next writer step may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion writer design. It must keep
the actual durable write path separate from this output-only apply gate.
