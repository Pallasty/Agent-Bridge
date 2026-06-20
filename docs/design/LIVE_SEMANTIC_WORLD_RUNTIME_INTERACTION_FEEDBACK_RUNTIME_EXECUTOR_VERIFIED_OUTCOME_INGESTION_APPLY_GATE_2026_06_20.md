# Live Semantic World Runtime — Runtime Executor Verified Outcome Ingestion Apply Gate

Date: 2026-06-20

Status: Draft implementation spec

## 1. Purpose

G21 adds the next narrow gate after G20:

```text
verified outcome ingestion execution commit
  -> verified outcome ingestion apply gate
  -> verified outcome ingestion writer
```

It answers one question:

> Has an explicit apply decision accepted the bounded G20 package as ready for
> a later verified outcome ingestion writer?

This remains output-only. It emits a bounded writer-ready package, but it does
not ingest #94 outcomes, persist the world verdict, write durable outcome
records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source commit must be G20:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit.v0`;
- `verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`;
- `next_allowed_gate=verified_outcome_ingestion_apply`;
- `ready_for_verified_outcome_ingestion_apply=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_ingestion_execution_commit_output_only=true`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  allowed by the source.

The explicit apply decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_apply_decision.v0
```

Required decision properties:

- `decision_kind=verified_outcome_ingestion_apply`;
- `decision=approved_for_verified_outcome_ingestion_writer`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`;
- `commit_package_confirmed=true`;
- `execution_preflight_package_confirmed=true`;
- `verified_outcome_package_confirmed=true`;
- `reviewer_attestation_present=true`;
- `evidence_lineage_preserved=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `writer_boundary_acknowledged=true`;
- `outcome_ingestion_allowed_by_this_tool=false`;
- `memory_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

## 3. Scope Matching

The apply decision must exactly match the G20 execution commit scope for:

- commit-decision id;
- source execution, ingestion, rewrite, and review decision ids;
- write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the apply gate.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate.v0",
  "verified_outcome_ingestion_apply_verdict": "ready_for_verified_outcome_ingestion_writer",
  "status": "ready",
  "reason": "verified_outcome_ingestion_apply_ready_for_writer",
  "next_allowed_gate": "verified_outcome_ingestion_writer",
  "verified_outcome_ingestion_apply": {
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
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

## 5. Boundary

G21 does not execute verified outcome ingestion. It only turns a ready G20
package plus an explicit apply decision into a bounded package for a later
writer slice.

The critical distinction is:

- `verified_outcome_ingestion_apply_verdict=ready_for_verified_outcome_ingestion_writer`:
  the next writer step may consume the package;
- `ready_for_verified_outcome_ingestion_writer=true`: the apply gate is
  satisfied;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion writer design. It must
consume the G21 package and still keep any durable write path isolated behind
its own implementation, audit, idempotency, and rollback checks.
