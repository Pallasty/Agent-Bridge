# Live Semantic World Runtime - Runtime Executor Verified Outcome Ingestion Admission Preflight

Date: 2026-06-21

Status: Draft implementation spec

## 1. Purpose

G28 adds the admission preflight after G27:

```text
verified outcome ingestion write-evidence review preflight
  -> verified outcome ingestion admission decision
  -> verified outcome ingestion execution
```

It answers one question:

> Does an explicit admission decision approve the scoped G27 review package for
> a later, separate verified-outcome ingestion execution gate?

This remains output-only. It validates the G27 review-preflight readiness,
explicit admission decision shape, scope, digest/readback/idempotency
confirmations, and boundary flags. It does not execute admission, ingest
outcomes, perform store writes, persist the world verdict, write durable outcome
records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source review preflight must be G27:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight.v0`;
- `verified_outcome_ingestion_write_evidence_review_preflight_verdict=ready_for_verified_outcome_ingestion_admission`;
- `next_allowed_gate=verified_outcome_ingestion_admission`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_admission=true`;
- all store-write confirmation, ack, readback, digest, idempotency, persisted
  key/digest, and reviewer attestation checks true;
- no store write, memory write, ingestion, world-verdict persistence, durable
  outcome record write, live store access, or MCP surface performed by the
  source tool.

The explicit admission decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_admission_decision.v0
```

Required admission properties:

- `admission_kind=verified_outcome_ingestion_admission`;
- `decision=approved_for_verified_outcome_ingestion_execution`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_admission_preflight_verdict=ready_for_verified_outcome_ingestion_admission`;
- `write_evidence_review_preflight_confirmed=true`;
- `write_evidence_review_decision_confirmed=true`;
- `verified_outcome_store_write_confirmed=true`;
- `store_ack_confirmed=true`;
- `record_readback_confirmed=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `operator_attestation_present=true`;
- `verified_outcome_ingestion_execution_allowed=false`;
- `outcome_ingestion_allowed_by_this_tool=false`;
- `memory_write_allowed=false`;
- `world_verdict_persisted_by_this_tool=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `verified_outcome_store_written_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`.

## 3. Scope Matching

The admission decision must exactly match the G27 review package for:

- review decision id and write-evidence id;
- store-write execution id;
- G24 persistence decision id and G23 source writer-execution id;
- writer, apply, and commit decision ids;
- source execution, ingestion, rewrite, and review decision ids;
- source durable write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the admission preflight.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight.v0",
  "verified_outcome_ingestion_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_execution",
  "status": "ready",
  "reason": "verified_outcome_ingestion_admission_preflight_ready_for_execution",
  "next_allowed_gate": "verified_outcome_ingestion_execution",
  "verified_outcome_ingestion_admission": {
    "admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
    "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
    "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
    "decision": "approved_for_verified_outcome_ingestion_execution",
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "write_evidence_review_preflight_confirmed": true,
    "write_evidence_review_decision_confirmed": true,
    "verified_outcome_store_write_confirmed": true,
    "store_ack_confirmed": true,
    "record_readback_confirmed": true,
    "outcome_record_digest_confirmed": true,
    "idempotency_key_confirmed": true,
    "ready_for_verified_outcome_ingestion_execution": true,
    "verified_outcome_ingestion_execution_allowed": false,
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

G28 does not execute verified-outcome ingestion. It only validates a separately
supplied admission decision and carries the bounded admission package forward.

The critical distinction is:

- `decision=approved_for_verified_outcome_ingestion_execution`: admission
  approval for a later execution gate;
- `verified_outcome_ingestion_execution_allowed=false`: this preflight does not
  itself allow or execute ingestion;
- `ready_for_verified_outcome_ingestion_execution=true`: a later slice may
  consume this package;
- `verified_outcome_ingested_by_this_tool=false`: no verified outcome was
  ingested here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion execution. It must consume
this admission package while preserving the separation between admission approval
and actual ingestion behavior.
