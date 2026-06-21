# Acceptance - Runtime Executor Verified Outcome Ingestion Admission Preflight

Date: 2026-06-21

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight -- --nocapture
```

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-admission --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_smoke -- --with-verified-outcome-ingestion-admission --format json --assert-ready-for-verified-outcome-ingestion-execution --assert-output-only
```

Expected:

- missing admission decision blocks with
  `explicit_verified_outcome_ingestion_admission_decision_required`;
- explicit scoped admission decision returns
  `ready_for_verified_outcome_ingestion_execution`;
- bad decision blocks on kind, approval, source verdict, verified verdict, G27
  review target, review confirmation, store-write confirmation, ack, readback,
  digest, idempotency, persisted key/digest confirmation, operator attestation,
  permission, boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_required`.

Expected ready fields:

- `verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `next_allowed_gate=verified_outcome_ingestion_execution`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `write_evidence_review_preflight_confirmed=true`;
- `write_evidence_review_decision_confirmed=true`;
- `verified_outcome_store_write_confirmed=true`;
- `store_ack_confirmed=true`;
- `record_readback_confirmed=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `operator_attestation_present=true`;
- `ready_for_verified_outcome_ingestion_execution=true`;
- `verified_outcome_ingestion_execution_allowed=false`;
- `verified_outcome_store_written_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G28 preflight can recognize that an explicit admission decision approves a
G27 review package for later execution. It cannot execute ingestion, perform
store writes, persist the verdict, write a durable outcome record, write memory,
or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_execution`: admission
  approval for a later execution gate;
- `verified_outcome_ingestion_execution_allowed=false`: this tool does not
  execute ingestion;
- `verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`:
  the next execution step may consume this package.

## 3. Next Slice

The next safe slice is verified outcome ingestion execution. It should stay
separate from this admission step and keep output-only defaults until an
explicit, audited execution boundary exists.
