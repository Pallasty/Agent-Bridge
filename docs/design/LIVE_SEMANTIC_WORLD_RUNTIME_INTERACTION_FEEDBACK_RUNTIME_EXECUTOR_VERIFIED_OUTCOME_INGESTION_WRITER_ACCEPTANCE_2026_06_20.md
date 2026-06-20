# Acceptance — Runtime Executor Verified Outcome Ingestion Writer

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_writer -- --nocapture
```

Expected:

- missing writer decision blocks with
  `explicit_verified_outcome_ingestion_writer_decision_required`;
- explicit scoped writer decision returns
  `ready_for_verified_outcome_ingestion_writer_execution`;
- bad writer decision blocks on kind, decision, source verdict, verified
  verdict, G21 review, package confirmations, payload, destination,
  idempotency, writer boundary, rollback, unsafe write flags, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_apply_gate_required`.

Expected ready fields:

- `verified_outcome_ingestion_writer_verdict=ready_for_verified_outcome_ingestion_writer_execution`;
- `next_allowed_gate=verified_outcome_ingestion_writer_execution`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_writer_execution=true`;
- `verified_outcome_ingestion_writer_output_only=true`;
- `verified_outcome_ingestion_writer_execution_allowed_after_gate=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G22 writer gate can emit a bounded writer-execution package from a scoped
G21 package plus explicit writer decision. It cannot persist the verdict, write
a durable outcome record, ingest outcomes, write memory, or expose MCP tools.

