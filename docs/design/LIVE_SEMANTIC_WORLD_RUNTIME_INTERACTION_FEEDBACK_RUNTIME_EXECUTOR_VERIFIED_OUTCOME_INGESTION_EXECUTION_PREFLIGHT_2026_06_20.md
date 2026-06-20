# Live Semantic World Runtime — Runtime Executor Verified Outcome Ingestion Execution Preflight

Date: 2026-06-20

Status: Draft implementation spec

## 1. Purpose

G19 adds the next narrow preflight after G18:

```text
verified outcome ingestion gate
  -> verified outcome ingestion execution preflight
  -> verified outcome ingestion execution commit
```

It answers one question:

> Has an explicit execution decision accepted the bounded G18 package as ready
> for a separate commit/execution step?

This remains output-only. It emits a bounded commit-ready package, but it does
not ingest #94 outcomes, persist the world verdict, write durable outcome
records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source gate must be G18:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_gate.v0`;
- `verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_ingestion_execution`;
- `next_allowed_gate=verified_outcome_ingestion_execution`;
- `ready_for_verified_outcome_ingestion_execution=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_package_emitted_by_this_tool=true`;
- `verified_outcome_ingestion_gate_output_only=true`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  allowed by the source.

The explicit execution decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_decision.v0
```

Required decision properties:

- `decision_kind=verified_outcome_ingestion_execution`;
- `decision=approved_for_verified_outcome_ingestion_execution_preflight`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_ingestion_execution`;
- `verified_outcome_package_confirmed=true`;
- `ingestion_gate_output_confirmed=true`;
- `reviewer_attestation_present=true`;
- `evidence_lineage_preserved=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `execution_boundary_acknowledged=true`;
- `outcome_ingestion_allowed=false`;
- `memory_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

## 3. Scope Matching

The execution decision must exactly match the G18 ingestion gate scope for:

- ingestion-decision id;
- source rewrite-decision id;
- source review-decision id;
- write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the preflight.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight.v0",
  "verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
  "status": "ready",
  "reason": "verified_outcome_ingestion_execution_preflight_ready_for_execution_commit",
  "next_allowed_gate": "verified_outcome_ingestion_execution_commit",
  "verified_outcome_ingestion_execution": {
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "ready_for_verified_outcome_ingestion_execution_commit": true,
    "verified_outcome_ingestion_execution_preflight_output_only": true,
    "verified_outcome_ingested_by_this_tool": false,
    "world_verdict_persisted_by_this_tool": false,
    "durable_outcome_record_written_by_this_tool": false,
    "memory_write_allowed": false,
    "outcome_ingestion_allowed": false
  }
}
```

## 5. Boundary

G19 does not execute ingestion. It only turns a ready G18 package plus an
explicit execution decision into a bounded package for a later commit/execution
slice.

The critical distinction is:

- `verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`:
  the next commit step may consume the package;
- `ready_for_verified_outcome_ingestion_execution_commit=true`: the preflight
  is satisfied;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion execution commit. It must
consume the G19 package and require its own commit decision before any durable
#94 ingestion behavior is considered.
