# G29 Execution Preflight Admission Source Acceptance

Date: 2026-06-21

## Commands

```bash
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight -- --nocapture
```

Expected: execution preflight tests pass for both legacy ingestion-gate source
and G28 admission-preflight source.

```bash
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke -- --from-verified-outcome-ingestion-admission-preflight --with-verified-outcome-ingestion-execution-decision --format json --assert-ready-for-verified-outcome-ingestion-execution-commit --assert-output-only
```

Expected: admission-source smoke returns
`ready_for_verified_outcome_ingestion_execution_commit`.

## Ready Fields

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`;
- `next_allowed_gate=verified_outcome_ingestion_execution_commit`;
- `source_admission_decision_id=verified_outcome_ingestion_admission_arrival_bath_move_002`;
- `source_write_evidence_review_decision_id=verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002`;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`;
- `ready_for_verified_outcome_ingestion_execution_commit=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`.

## Blocking Cases

The fixture covers:

- missing execution decision from a direct G28 admission preflight input;
- non-ready G28 admission preflight verdict;
- admission next-gate mismatch;
- admission nested ready flag false;
- source/verified verdict drift;
- unsafe source boundary flags;
- missing admission preflight confirmation;
- missing admission decision confirmation;
- admission decision scope mismatch;
- outcome digest mismatch.

## Compatibility

The older G18 ingestion-gate source path remains supported and still uses
`source_verified_outcome_ingestion_gate_scope`. The G29 path uses
`source_verified_outcome_ingestion_admission_scope` without changing the
execution preflight schema.
