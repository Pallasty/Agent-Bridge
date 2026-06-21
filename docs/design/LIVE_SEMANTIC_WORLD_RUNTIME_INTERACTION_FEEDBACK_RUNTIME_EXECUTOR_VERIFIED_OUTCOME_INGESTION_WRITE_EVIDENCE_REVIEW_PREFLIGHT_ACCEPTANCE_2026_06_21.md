# Acceptance - Runtime Executor Verified Outcome Ingestion Write-Evidence Review Preflight

Date: 2026-06-21

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight -- --nocapture
```

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-write-evidence-review --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_smoke -- --with-verified-outcome-ingestion-write-evidence-review --format json --assert-ready-for-verified-outcome-ingestion-admission --assert-output-only
```

Expected:

- missing review decision blocks with
  `explicit_verified_outcome_ingestion_write_evidence_review_decision_required`;
- explicit scoped review decision returns
  `ready_for_verified_outcome_ingestion_admission`;
- bad review blocks on kind, approval, source verdict, verified verdict, G26
  review target, store-write confirmation, ack, readback, digest, idempotency,
  persisted key/digest confirmation, reviewer attestation, permission,
  boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_write_evidence_preflight_required`.

Expected ready fields:

- `verified_outcome_ingestion_write_evidence_review_preflight_verdict=ready_for_verified_outcome_ingestion_admission`;
- `next_allowed_gate=verified_outcome_ingestion_admission`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_store_write_confirmed=true`;
- `store_ack_confirmed=true`;
- `record_readback_confirmed=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `reviewer_attestation_present=true`;
- `ready_for_verified_outcome_ingestion_admission=true`;
- `verified_outcome_admission_allowed=false`;
- `verified_outcome_store_written_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

## 2. Boundary

This G27 preflight can recognize that an explicit review decision approves a
G26 write-evidence packet for later admission. It cannot execute admission,
ingest outcomes, perform store writes, persist the verdict, write a durable
outcome record, write memory, or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_admission`: review approval
  for a later gate;
- `verified_outcome_admission_allowed=false`: this tool does not admit the
  outcome;
- `verified_outcome_ingestion_write_evidence_review_preflight_verdict=ready_for_verified_outcome_ingestion_admission`:
  the next admission step may consume this package.

## 3. Next Slice

The next safe slice is verified outcome ingestion admission. It should stay
separate from this review step and keep the same output-only defaults until an
explicit, audited admission boundary exists.
