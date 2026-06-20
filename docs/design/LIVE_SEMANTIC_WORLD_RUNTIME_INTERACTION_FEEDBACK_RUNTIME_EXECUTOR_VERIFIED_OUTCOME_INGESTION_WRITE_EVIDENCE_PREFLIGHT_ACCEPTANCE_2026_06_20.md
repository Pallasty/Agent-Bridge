# Acceptance - Runtime Executor Verified Outcome Ingestion Write-Evidence Preflight

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight -- --nocapture
```

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-write-evidence --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_smoke -- --with-verified-outcome-ingestion-write-evidence --format json --assert-ready-for-verified-outcome-ingestion-write-evidence-review --assert-output-only
```

Expected:

- missing write evidence blocks with
  `explicit_verified_outcome_ingestion_write_evidence_required`;
- explicit scoped write evidence returns
  `ready_for_verified_outcome_ingestion_write_evidence_review`;
- bad evidence blocks on kind, source verdict, verified verdict, G25 review,
  store observation, ack, readback, digest, idempotency, key/digest mismatch,
  permission, boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_required`.

Expected ready fields:

- `verified_outcome_ingestion_write_evidence_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence_review`;
- `next_allowed_gate=verified_outcome_ingestion_write_evidence_review`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_store_write_observed=true`;
- `store_write_acknowledged=true`;
- `record_readback_verified=true`;
- `outcome_record_digest_verified=true`;
- `idempotency_key_confirmed=true`;
- `ready_for_verified_outcome_ingestion_write_evidence_review=true`;
- `verified_outcome_store_written_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G26 preflight can recognize evidence that an external verified-outcome
store write happened and was read back. It cannot execute the write, persist the
verdict, write a durable outcome record, ingest #94 outcomes, write memory, or
expose MCP tools.

The critical distinction is:

- `verified_outcome_store_write_observed=true`: the evidence packet reports an
  external write;
- `verified_outcome_store_written_by_this_tool=false`: this tool did not write;
- `verified_outcome_ingestion_write_evidence_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence_review`:
  the next review step may consume this package.

## 3. Next Slice

The next safe slice is verified outcome ingestion write-evidence review. It
must keep evidence review separate from ingestion/admission.
