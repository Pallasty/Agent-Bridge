# Acceptance - Runtime Executor Verified Outcome Ingestion Store-Write Execution Preflight

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight -- --nocapture
```

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-store-write-execution-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_smoke -- --with-verified-outcome-ingestion-store-write-execution-decision --format json --assert-ready-for-verified-outcome-ingestion-write-evidence --assert-output-only
```

Expected:

- missing store-write execution decision blocks with
  `explicit_verified_outcome_ingestion_store_write_execution_decision_required`;
- explicit scoped store-write execution decision returns
  `ready_for_verified_outcome_ingestion_write_evidence`;
- bad store-write execution decision blocks on kind, decision, source verdict,
  verified verdict, G24 review, package confirmations, target, digest,
  idempotency, transaction plan, rollback, permission, boundary, and scope
  errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_persistence_required`.

Expected ready fields:

- `verified_outcome_ingestion_store_write_execution_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence`;
- `next_allowed_gate=verified_outcome_ingestion_write_evidence`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_write_evidence=true`;
- `verified_outcome_ingestion_store_write_execution_preflight_output_only=true`;
- `verified_outcome_write_evidence_allowed_after_store_write_preflight=true`;
- `verified_outcome_store_write_execution_allowed=false`;
- `verified_outcome_store_written_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G25 preflight can emit a bounded write-evidence package from a scoped G24
package plus explicit store-write execution decision. It cannot write the
store, persist the verdict, write a durable outcome record, ingest #94
outcomes, write memory, or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_write_evidence`: explicit
  decision authorizes package emission for the next write-evidence slice;
- `verified_outcome_ingestion_store_write_execution_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence`:
  the next evidence step may consume this package;
- `verified_outcome_store_write_execution_allowed=false`: no store write
  happened here;
- `verified_outcome_store_written_by_this_tool=false`: this tool did not write
  a verified outcome record;
- `world_verdict_persisted_by_this_tool=false`: this tool did not persist a
  verdict change.

## 3. Next Slice

The next safe slice is verified outcome ingestion write-evidence preflight. It
must keep proof of the actual store write separate from this output-only
preflight gate.
