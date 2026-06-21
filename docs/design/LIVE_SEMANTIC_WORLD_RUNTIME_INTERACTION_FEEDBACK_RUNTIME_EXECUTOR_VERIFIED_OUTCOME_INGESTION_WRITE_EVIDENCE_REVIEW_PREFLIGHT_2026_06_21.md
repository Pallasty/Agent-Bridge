# Live Semantic World Runtime - Runtime Executor Verified Outcome Ingestion Write-Evidence Review Preflight

Date: 2026-06-21

Status: Draft implementation spec

## 1. Purpose

G27 adds the review preflight after G26:

```text
verified outcome ingestion write-evidence preflight
  -> verified outcome ingestion write-evidence review decision
  -> verified outcome ingestion admission
```

It answers one question:

> Does an explicit review decision approve the scoped G26 write-evidence packet
> for a later, separate verified-outcome ingestion admission gate?

This remains output-only. It validates review shape, source evidence readiness,
scope, digest, readback confirmation, and boundary flags. It does not admit or
ingest outcomes, execute a store write, persist the world verdict, write durable
outcome records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source write-evidence preflight must be G26:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight.v0`;
- `verified_outcome_ingestion_write_evidence_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence_review`;
- `next_allowed_gate=verified_outcome_ingestion_write_evidence_review`;
- `ready_for_verified_outcome_ingestion_write_evidence_review=true`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- all store-write observation, ack, readback, digest, and idempotency checks
  true;
- no store write, memory write, ingestion, world-verdict persistence, durable
  outcome record write, live store access, or MCP surface performed by the
  source tool.

The explicit review decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_write_evidence_review_decision.v0
```

Required review properties:

- `review_kind=verified_outcome_ingestion_write_evidence_review`;
- `decision=approved_for_verified_outcome_ingestion_admission`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_write_evidence_preflight_verdict=ready_for_verified_outcome_ingestion_write_evidence_review`;
- `verified_outcome_store_write_confirmed=true`;
- `store_ack_confirmed=true`;
- `record_readback_confirmed=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `reviewer_attestation_present=true`;
- `verified_outcome_admission_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`;
- `memory_write_allowed=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `verified_outcome_store_written_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`.

## 3. Scope Matching

The review decision must exactly match the G26 write-evidence scope for:

- write-evidence id;
- store-write execution id;
- G24 persistence decision id and G23 source writer-execution id;
- writer, apply, and commit decision ids;
- source execution, ingestion, rewrite, and review decision ids;
- source durable write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the review preflight.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight.v0",
  "verified_outcome_ingestion_write_evidence_review_preflight_verdict": "ready_for_verified_outcome_ingestion_admission",
  "status": "ready",
  "reason": "verified_outcome_ingestion_write_evidence_review_preflight_ready_for_admission",
  "next_allowed_gate": "verified_outcome_ingestion_admission",
  "verified_outcome_ingestion_write_evidence_review": {
    "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
    "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
    "decision": "approved_for_verified_outcome_ingestion_admission",
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "verified_outcome_store_write_confirmed": true,
    "store_ack_confirmed": true,
    "record_readback_confirmed": true,
    "outcome_record_digest_confirmed": true,
    "idempotency_key_confirmed": true,
    "ready_for_verified_outcome_ingestion_admission": true,
    "verified_outcome_admission_allowed": false,
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

G27 does not perform admission. It only validates a separately supplied review
decision and carries the bounded evidence review package forward.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_admission`: the reviewer
  approves entering a later admission gate;
- `verified_outcome_admission_allowed=false`: this preflight does not itself
  allow or execute admission;
- `ready_for_verified_outcome_ingestion_admission=true`: a later slice may
  consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no verified outcome was
  ingested here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion admission. It must consume
this review package while preserving the separation between review approval and
actual admission/ingestion behavior.
