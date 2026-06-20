# Acceptance - Runtime Executor Verified Outcome Ingestion Persistence Gate

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence -- --nocapture
```

Expected:

- missing persistence decision blocks with
  `explicit_verified_outcome_ingestion_persistence_decision_required`;
- explicit scoped persistence decision returns
  `ready_for_verified_outcome_ingestion_store_write`;
- bad persistence decision blocks on kind, decision, source verdict, verified
  verdict, G23 review, package confirmations, target, digest, idempotency,
  transaction plan, rollback, permission, boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_writer_execution_required`.

Expected ready fields:

- `verified_outcome_ingestion_persistence_verdict=ready_for_verified_outcome_ingestion_store_write`;
- `next_allowed_gate=verified_outcome_ingestion_store_write`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_store_write=true`;
- `verified_outcome_ingestion_persistence_output_only=true`;
- `verified_outcome_ingestion_store_write_allowed_after_persistence=true`;
- `verified_outcome_store_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G24 persistence gate can emit a bounded store-write package from a scoped
G23 package plus explicit persistence decision. It cannot persist the verdict,
write a durable outcome record, ingest #94 outcomes, write memory, or expose MCP
tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_store_write`: explicit
  decision authorizes package emission for the next store-write slice;
- `verified_outcome_ingestion_persistence_verdict=ready_for_verified_outcome_ingestion_store_write`:
  the next store-write step may consume this package;
- `verified_outcome_store_write_allowed=false`: no store write happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion store-write design. It must
keep the actual durable write path separate from this output-only persistence
gate.
