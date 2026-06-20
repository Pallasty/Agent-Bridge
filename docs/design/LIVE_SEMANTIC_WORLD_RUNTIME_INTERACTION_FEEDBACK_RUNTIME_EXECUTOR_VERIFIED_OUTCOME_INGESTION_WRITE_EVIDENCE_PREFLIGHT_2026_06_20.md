# Live Semantic World Runtime - Runtime Executor Verified Outcome Ingestion Write-Evidence Preflight

Date: 2026-06-20

Status: Draft implementation spec

## 1. Purpose

G26 adds the narrow preflight after G25:

```text
verified outcome ingestion store-write execution preflight
  -> verified outcome ingestion write evidence
  -> verified outcome ingestion write-evidence review
```

It answers one question:

> Does an externally supplied write-evidence packet prove that the scoped
> verified-outcome record was written and read back after G25?

This remains output-only. It validates evidence shape, scope, digest, and
readback claims. It does not perform the store write, ingest #94 outcomes,
persist the world verdict, write durable outcome records, write memory,
register MCP tools, or query a live runtime.

## 2. Required Input

The source store-write execution preflight must be G25:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight.v0`;
- `verified_outcome_ingestion_store_write_execution_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence`;
- `next_allowed_gate=verified_outcome_ingestion_write_evidence`;
- `ready_for_verified_outcome_ingestion_write_evidence=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  performed by the source tool.

The explicit write-evidence packet must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_write_evidence.v0
```

Required evidence properties:

- `evidence_kind=verified_outcome_ingestion_write_evidence`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_store_write_execution_decision=approved_for_verified_outcome_ingestion_write_evidence`;
- `verified_outcome_store_write_observed=true`;
- `store_write_acknowledged=true`;
- `record_readback_verified=true`;
- `outcome_record_digest_verified=true`;
- `idempotency_key_confirmed=true`;
- `write_destination`, `outcome_record_key`, and `outcome_record_digest`
  present;
- persisted key and digest equal the supplied record key and digest;
- `verified_outcome_store_written_by_this_tool=false`;
- `outcome_ingestion_allowed_by_this_tool=false`;
- `memory_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

## 3. Scope Matching

The write evidence must exactly match the G25 store-write execution scope for:

- store-write execution id;
- G24 persistence decision id and source G23 writer-execution id;
- writer, apply, and commit decision ids;
- source execution, ingestion, rewrite, and review decision ids;
- source durable write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the preflight.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight.v0",
  "verified_outcome_ingestion_write_evidence_preflight_verdict": "ready_for_verified_outcome_ingestion_write_evidence_review",
  "status": "ready",
  "reason": "verified_outcome_ingestion_write_evidence_preflight_ready_for_evidence_review",
  "next_allowed_gate": "verified_outcome_ingestion_write_evidence_review",
  "verified_outcome_ingestion_write_evidence": {
    "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
    "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "verified_outcome_store_write_observed": true,
    "store_write_acknowledged": true,
    "record_readback_verified": true,
    "outcome_record_digest_verified": true,
    "idempotency_key_confirmed": true,
    "ready_for_verified_outcome_ingestion_write_evidence_review": true,
    "verified_outcome_store_written_by_this_tool": false,
    "verified_outcome_ingested_by_this_tool": false,
    "world_verdict_persisted_by_this_tool": false,
    "durable_outcome_record_written_by_this_tool": false,
    "memory_write_allowed": false,
    "outcome_ingestion_allowed_by_this_tool": false
  }
}
```

## 5. Boundary

G26 does not execute the store write. It only validates a separately supplied
write-evidence packet and carries the bounded package forward for later review.

The critical distinction is:

- `verified_outcome_store_write_observed=true`: the evidence packet claims an
  external write was observed;
- `verified_outcome_store_written_by_this_tool=false`: this preflight did not
  write the store;
- `ready_for_verified_outcome_ingestion_write_evidence_review=true`: a later
  review slice may judge the evidence;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion write-evidence review. It must
review this evidence before any ingestion/admission path can move forward.
