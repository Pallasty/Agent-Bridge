# Acceptance — Runtime Executor Verified Outcome Ingestion Execution Preflight

Date: 2026-06-20

Status: ACCEPTED_G19_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_OUTPUT_ONLY / G29_ACCEPTS_VERIFIED_OUTCOME_INGESTION_ADMISSION_PREFLIGHT_SOURCE

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight -- --nocapture
```

Expected:

- missing execution decision blocks with
  `explicit_verified_outcome_ingestion_execution_decision_required`;
- explicit scoped execution decision returns
  `ready_for_verified_outcome_ingestion_execution_commit`;
- direct G28 admission preflight source without an execution decision blocks
  with `explicit_verified_outcome_ingestion_execution_decision_required`;
- explicit scoped G28 admission preflight decision returns
  `ready_for_verified_outcome_ingestion_execution_commit`;
- bad execution decision blocks on kind, decision, source verdict, verified
  verdict, G18 review, package confirmation, gate output confirmation,
  attestation, lineage, digest, idempotency, permission, boundary, and scope
  errors;
- bad G28 admission preflight source or decision blocks on admission readiness,
  next gate, world verdicts, output-only boundary, admission review,
  admission-preflight confirmation, admission-decision confirmation, and scope
  errors;
- wrong source input blocks with
  `runtime_executor_verified_outcome_ingestion_gate_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-execution-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke -- --with-verified-outcome-ingestion-execution-decision --format json --assert-ready-for-verified-outcome-ingestion-execution-commit --assert-output-only
```

G28 admission-source ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke -- --from-verified-outcome-ingestion-admission-preflight --with-verified-outcome-ingestion-execution-decision --format json --assert-ready-for-verified-outcome-ingestion-execution-commit --assert-output-only
```

Expected ready fields:

- `verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`;
- `next_allowed_gate=verified_outcome_ingestion_execution_commit`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_execution_commit=true`;
- `verified_outcome_ingestion_execution_preflight_output_only=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`.

For the G28 admission-source smoke, expected ready fields also include:

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`;
- `source_verified_outcome_ingestion_gate=null`;
- `source_verified_outcome_ingestion_admission_preflight` present.

## 2. Boundary

This G19/G29 preflight can emit a bounded commit-ready package from a scoped G18
or G28 package plus explicit execution decision. It cannot persist the verdict,
write a durable outcome record, ingest #94 outcomes, write memory, or expose MCP
tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_execution_preflight`:
  explicit decision authorizes package emission for the next commit slice;
- `verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`:
  the next commit gate may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion execution commit. It must
require its own commit decision and must not treat a ready G19 package as
already ingested or persisted.
