# Acceptance - Runtime Executor Verified Outcome Ingestion Writer Execution Gate

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution -- --nocapture
```

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-writer-execution-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_smoke -- --with-verified-outcome-ingestion-writer-execution-decision --format json --assert-ready-for-verified-outcome-ingestion-persistence --assert-output-only
```

Expected:

- missing writer-execution decision blocks with
  `explicit_verified_outcome_ingestion_writer_execution_decision_required`;
- explicit scoped writer-execution decision returns
  `ready_for_verified_outcome_ingestion_persistence`;
- bad writer-execution decision blocks on kind, decision, source verdict,
  verified verdict, G22 review, package confirmations, destination, digest,
  idempotency, transaction plan, rollback, permission, boundary, and scope
  errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_writer_required`.

Expected ready fields:

- `verified_outcome_ingestion_writer_execution_verdict=ready_for_verified_outcome_ingestion_persistence`;
- `next_allowed_gate=verified_outcome_ingestion_persistence`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_persistence=true`;
- `verified_outcome_ingestion_writer_execution_output_only=true`;
- `verified_outcome_ingestion_persistence_allowed_after_execution=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G23 writer-execution gate can emit a bounded persistence package from a
scoped G22 package plus explicit writer-execution decision. It cannot persist
the verdict, write a durable outcome record, ingest #94 outcomes, write memory,
or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_persistence`: explicit
  decision authorizes package emission for the next persistence slice;
- `verified_outcome_ingestion_writer_execution_verdict=ready_for_verified_outcome_ingestion_persistence`:
  the next persistence step may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion persistence design. It must
keep the actual durable write path separate from this output-only execution
gate.
