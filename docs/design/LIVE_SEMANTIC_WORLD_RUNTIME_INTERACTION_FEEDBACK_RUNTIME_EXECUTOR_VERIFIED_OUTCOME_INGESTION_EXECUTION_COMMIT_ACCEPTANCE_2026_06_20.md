# Acceptance — Runtime Executor Verified Outcome Ingestion Execution Commit

Date: 2026-06-20

Status: Draft acceptance notes / G30_ACCEPTS_ADMISSION_SOURCE_EXECUTION_PREFLIGHT

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit -- --nocapture
```

Expected:

- missing commit decision blocks with
  `explicit_verified_outcome_ingestion_execution_commit_decision_required`;
- explicit scoped commit decision returns
  `ready_for_verified_outcome_ingestion_apply`;
- explicit scoped commit decision over a G29 admission-source execution
  preflight returns `ready_for_verified_outcome_ingestion_apply`;
- bad commit decision blocks on kind, decision, source verdict, verified
  verdict, G19 review, package confirmations, attestation, lineage, digest,
  idempotency, permission, boundary, and scope errors;
- bad admission-source commit decision blocks on admission-preflight
  confirmation, admission-decision confirmation, admission-decision scope, and
  store-write scope errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_execution_preflight_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-execution-commit-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke -- --with-verified-outcome-ingestion-execution-commit-decision --format json --assert-ready-for-verified-outcome-ingestion-apply --assert-output-only
```

G29 admission-source ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke -- --from-verified-outcome-ingestion-admission-preflight --with-verified-outcome-ingestion-execution-commit-decision --format json --assert-ready-for-verified-outcome-ingestion-apply --assert-output-only
```

Expected ready fields:

- `verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`;
- `next_allowed_gate=verified_outcome_ingestion_apply`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_apply=true`;
- `verified_outcome_ingestion_execution_commit_output_only=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`.

For the G29 admission-source smoke, expected ready fields also include:

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `source_admission_decision_id=verified_outcome_ingestion_admission_arrival_bath_move_002`;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`.

## 2. Boundary

This G20/G30 commit gate can emit a bounded apply-ready package from a scoped
G19 package plus explicit commit decision. It cannot persist the verdict, write
a durable outcome record, ingest #94 outcomes, write memory, or expose MCP
tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_apply`: explicit decision
  authorizes package emission for the next apply slice;
- `verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`:
  the next apply gate may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion apply. It must require its
own apply decision and must not treat a ready G20 package as already ingested
or persisted.
