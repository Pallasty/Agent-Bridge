# Acceptance - Runtime Executor Verified Outcome Ingestion Writer Gate

Date: 2026-06-20
Updated: 2026-06-21

Status: Implemented acceptance notes

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
- explicit scoped writer decision over a G31 admission-source apply gate returns
  `ready_for_verified_outcome_ingestion_writer_execution` while preserving
  admission, write-evidence, store-write, persistence, writer, apply, commit,
  prior execution, and source write-evidence ids;
- bad writer decision blocks on kind, decision, source verdict, verified
  verdict, G21 review, package confirmations, payload, destination,
  idempotency, rollback, permission, boundary, and scope errors;
- bad admission-source writer decision blocks on admission-preflight
  confirmation, admission-decision confirmation, admission-decision scope, and
  store-write scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_apply_gate_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-writer-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_smoke -- --with-verified-outcome-ingestion-writer-decision --format json --assert-ready-for-verified-outcome-ingestion-writer-execution --assert-output-only
```

Admission-source ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_smoke -- --from-verified-outcome-ingestion-admission-source-apply-gate --with-verified-outcome-ingestion-writer-decision --format json --assert-ready-for-verified-outcome-ingestion-writer-execution --assert-output-only
```

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

For the admission-source ready smoke, expected ready fields also include:

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `source_admission_decision_id=verified_outcome_ingestion_admission_arrival_bath_move_002`;
- `source_write_evidence_review_decision_id=verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002`;
- `store_write_execution_id=verified_outcome_ingestion_store_write_execution_arrival_bath_move_002`;
- `persistence_decision_id=verified_outcome_ingestion_persistence_arrival_bath_move_002`;
- `persistence_source_execution_id=verified_outcome_ingestion_writer_execution_arrival_bath_move_002`;
- `source_writer_decision_id=verified_outcome_ingestion_writer_arrival_bath_move_002`;
- `source_apply_decision_id=verified_outcome_ingestion_apply_arrival_bath_move_002`;
- `source_commit_decision_id=verified_outcome_ingestion_execution_commit_arrival_bath_move_002`;
- `source_prior_execution_decision_id=verified_outcome_ingestion_execution_arrival_bath_move_002`;
- `source_write_evidence_id=durable_outcome_record_write_evidence_arrival_bath_move_002`;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`.

## 2. Boundary

This G22/G32 writer gate can emit a bounded writer-execution package from a
scoped G21 package, or from a scoped G31 admission-source package, plus an
explicit writer decision. It cannot persist the verdict, write a durable
outcome record, ingest #94 outcomes, write memory, or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_writer_execution`: explicit
  decision authorizes package emission for the next writer-execution slice;
- `verified_outcome_ingestion_writer_verdict=ready_for_verified_outcome_ingestion_writer_execution`:
  the next writer-execution step may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion writer execution lineage
propagation. It must keep the actual durable write path separate from this
output-only writer gate.
