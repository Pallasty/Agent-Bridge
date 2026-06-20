# Live Semantic World Runtime — Runtime Executor Durable Outcome Record Write-Evidence Review Preflight

Date: 2026-06-18

Status: Draft implementation spec

## 1. Purpose

G16 adds the next narrow gate after G15:

```text
durable outcome record write-evidence preflight
  -> durable outcome record write-evidence review preflight
  -> explicit world-verdict rewrite gate
```

It answers one question:

> Has an explicit reviewer accepted the scoped durable outcome record write
> evidence as sufficient to enter a later world-verdict rewrite gate?

This is still a preflight and review-envelope step. It does not perform the
review itself, write records, write memory, ingest #94 outcomes, register MCP
tools, or rewrite the world verdict.

## 2. Required Input

The source preflight must be G15:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight.v0`;
- `durable_outcome_record_write_evidence_preflight_verdict=ready_for_durable_outcome_record_write_evidence_review`;
- `source_world_verdict=not_verified`;
- `ready_for_durable_outcome_record_write_evidence_review=true`;
- write observed, store ack, readback, digest, idempotency, persisted key, and
  persisted digest evidence all intact;
- no write, memory, ingestion, or verdict rewrite allowed by the source.

The explicit review decision must use:

```text
agent_bridge.lswr.runtime_executor.durable_outcome_record_write_evidence_review_decision.v0
```

Required review properties:

- `review_kind=durable_outcome_record_write_evidence_review`;
- `decision=approved_for_world_verdict_rewrite_gate`;
- `source_world_verdict=not_verified`;
- `reviewed_write_evidence_preflight_verdict=ready_for_durable_outcome_record_write_evidence_review`;
- `durable_outcome_record_write_confirmed=true`;
- `store_ack_confirmed=true`;
- `record_readback_confirmed=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `reviewer_attestation_present=true`;
- `outcome_ingestion_allowed=false`;
- `memory_write_allowed=false`;
- `world_verdict_rewrite_allowed=false`;
- `durable_outcome_record_written_by_this_tool=false`.

## 3. Scope Matching

The review decision must exactly match the G15 write evidence scope for:

- write-evidence id;
- store-write execution id;
- persistence, record-write execution, record-write, write implementation,
  durable ingestion execution, gate, review, verification, and runtime
  application evidence ids;
- invocation request, world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, write plan,
  destination, record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the preflight.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight.v0",
  "durable_outcome_record_write_evidence_review_preflight_verdict": "ready_for_world_verdict_rewrite_gate",
  "status": "ready",
  "reason": "durable_outcome_record_write_evidence_review_preflight_ready_for_world_verdict_rewrite_gate",
  "next_allowed_gate": "world_verdict_rewrite_gate"
}
```

The ready output permits only entering a later explicit gate. It does not
rewrite `source_world_verdict=not_verified`.

## 5. Guardrails

G16 keeps these invariants explicit:

- `read_only=true`;
- `mutation_surface=none`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`;
- `queries_live_runtime=false`;
- `requires_ready_durable_outcome_record_write_evidence_preflight=true`;
- `requires_explicit_durable_outcome_record_write_evidence_review_decision=true`;
- `review_kind=durable_outcome_record_write_evidence_review`;
- `performs_durable_outcome_record_write_evidence_review=false`;
- `durable_outcome_record_written=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `persists_outcome_record=false`;
- `feedback_changes_world_verdict_allowed=false`.

## 6. Boundary

Accepted by this slice:

- validating a scoped external review decision;
- carrying accepted write-evidence review to the next explicit gate;
- keeping the durable write evidence and review evidence separate.

Still not accepted:

- performing durable outcome record writes;
- memory writes;
- #94 ingestion;
- MCP registration or profile exposure;
- world verdict rewrite;
- treating durable write evidence review as the actual verdict rewrite.

## 7. Next Slice

The next safe slice is G17, an explicit world-verdict rewrite gate. It consumes
the accepted G16 output and still requires an explicit rewrite decision before
emitting a bounded `verified` verdict package. That package remains output-only
until a later verified outcome ingestion gate consumes it.
