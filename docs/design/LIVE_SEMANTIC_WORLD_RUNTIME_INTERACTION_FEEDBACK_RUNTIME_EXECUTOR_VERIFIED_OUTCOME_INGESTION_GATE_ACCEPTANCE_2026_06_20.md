# Acceptance — Runtime Executor Verified Outcome Ingestion Gate

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_gate -- --nocapture
```

Expected:

- missing ingestion decision blocks with
  `explicit_verified_outcome_ingestion_decision_required`;
- explicit scoped ingestion-gate decision returns
  `ready_for_verified_outcome_ingestion_execution`;
- bad ingestion decision blocks on kind, decision, source verdict, rewritten
  verdict, G17 review, claim, rewrite output confirmation, attestation,
  lineage, digest, idempotency, permission, boundary, and scope errors;
- wrong source input blocks with
  `runtime_executor_world_verdict_rewrite_gate_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_smoke -- --format json --assert-blocked-without-verified-outcome-ingestion-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_smoke -- --with-verified-outcome-ingestion-decision --format json --assert-ready-for-verified-outcome-ingestion-execution --assert-output-only
```

Expected ready fields:

- `verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_ingestion_execution`;
- `next_allowed_gate=verified_outcome_ingestion_execution`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_execution=true`;
- `verified_outcome_package_emitted_by_this_tool=true`;
- `verified_outcome_ingested_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`.

## 2. Boundary

This G18 gate can emit a bounded verified outcome ingestion package from a
scoped G17 package plus explicit ingestion-gate decision. It cannot persist
the verdict, write a durable outcome record, ingest #94 outcomes, write memory,
or expose MCP tools.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_gate`: explicit decision
  authorizes package emission for the next execution slice;
- `verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_ingestion_execution`:
  the next execution gate may consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here.

## 3. Next Slice

The next safe slice is verified outcome ingestion execution. It must require
its own execution decision and must not treat a ready G18 package as already
ingested or persisted.
