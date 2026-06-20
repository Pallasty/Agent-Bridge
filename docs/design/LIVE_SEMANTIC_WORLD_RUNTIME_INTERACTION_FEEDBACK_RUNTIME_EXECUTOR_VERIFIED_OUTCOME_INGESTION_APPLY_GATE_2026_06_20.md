# LSWR Runtime Executor Verified Outcome Ingestion Apply Gate

Status: PROPOSED

Date: 2026-06-20

## Purpose

G21 adds a pure `verified_outcome_ingestion_apply` gate after the G20
`verified_outcome_ingestion_execution_commit` package. It is the final
admission package before a separate writer may ingest the verified outcome.

The gate does not perform ingestion. It emits a bounded writer-ready package
only when an explicit apply decision confirms the G20 commit package, evidence
lineage, idempotency key, persisted outcome record key, and digest.

## Source Gate

The source must be:

```text
agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit.v0
```

Required source signals:

- `verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`;
- `next_allowed_gate=verified_outcome_ingestion_apply`;
- `ready_for_verified_outcome_ingestion_apply=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- source package remains output-only and has not written memory, persisted a
  verdict, or ingested the verified outcome.

## Decision Schema

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_apply_decision.v0
```

Required decision signals:

- `decision_kind=verified_outcome_ingestion_apply`;
- `decision=approved_for_verified_outcome_ingestion_writer`;
- `reviewed_verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`;
- confirmation flags for the commit package, execution preflight package,
  verified outcome package, reviewer attestation, evidence lineage, outcome
  record digest, idempotency key, persisted key, persisted digest, and writer
  boundary.

## Output Contract

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate.v0",
  "verified_outcome_ingestion_apply_verdict": "ready_for_verified_outcome_ingestion_writer",
  "next_allowed_gate": "verified_outcome_ingestion_writer",
  "verified_outcome_ingestion_apply": {
    "ready_for_verified_outcome_ingestion_writer": true,
    "verified_outcome_ingestion_apply_gate_output_only": true,
    "verified_outcome_ingestion_writer_allowed_after_gate": true,
    "verified_outcome_ingested_by_this_tool": false,
    "world_verdict_persisted_by_this_tool": false,
    "durable_outcome_record_written_by_this_tool": false,
    "memory_write_allowed": false,
    "outcome_ingestion_allowed_by_this_tool": false
  }
}
```

The next gate is a separate verified outcome ingestion writer. This pure gate
must not write state, access the store, expose an MCP tool, persist a world
verdict, or ingest the verified outcome itself.

