# Live Semantic World Runtime — Runtime Executor World Verdict Rewrite Gate

Date: 2026-06-20

Status: Draft implementation spec

## 1. Purpose

G17 adds the next narrow gate after G16:

```text
durable outcome record write-evidence review preflight
  -> explicit world-verdict rewrite gate
  -> verified outcome ingestion gate
```

It answers one question:

> Has an explicit rewrite decision accepted the reviewed durable outcome record
> write evidence as sufficient to emit a bounded `verified` world-verdict
> package for the next ingestion gate?

This is an output-only gate. It can emit the bounded rewrite result, but it does
not persist the world verdict, write durable outcome records, write memory,
ingest #94 verified outcomes, register MCP tools, or query a live runtime.

## 2. Required Input

The source preflight must be G16:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight.v0`;
- `durable_outcome_record_write_evidence_review_preflight_verdict=ready_for_world_verdict_rewrite_gate`;
- `source_world_verdict=not_verified`;
- `ready_for_world_verdict_rewrite_gate=true`;
- review decision was `approved_for_world_verdict_rewrite_gate`;
- the source preflight did not rewrite the verdict;
- no write, memory, ingestion, persistence, or MCP surface allowed by the
  source.

The explicit rewrite decision must use:

```text
agent_bridge.lswr.runtime_executor.world_verdict_rewrite_decision.v0
```

Required decision properties:

- `decision_kind=world_verdict_rewrite`;
- `decision=rewrite_world_verdict_to_verified`;
- `source_world_verdict=not_verified`;
- `target_world_verdict=verified`;
- `reviewed_write_evidence_review_preflight_verdict=ready_for_world_verdict_rewrite_gate`;
- `verified_outcome_claim_present=true`;
- `reviewer_attestation_present=true`;
- `evidence_lineage_preserved=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `world_verdict_rewrite_allowed=true`;
- `outcome_ingestion_allowed=false`;
- `memory_write_allowed=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

## 3. Scope Matching

The rewrite decision must exactly match the G16 reviewed write-evidence scope
for:

- review-decision id;
- write-evidence id;
- store-write execution id;
- persistence, record-write execution, record-write, write implementation,
  durable ingestion execution, gate, review, verification, and runtime
  application evidence ids;
- invocation request, world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, write plan,
  destination, record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the gate.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_world_verdict_rewrite_gate.v0",
  "world_verdict_rewrite_gate_verdict": "ready_for_verified_outcome_ingestion_gate",
  "status": "ready",
  "reason": "world_verdict_rewrite_gate_ready_for_verified_outcome_ingestion_gate",
  "next_allowed_gate": "verified_outcome_ingestion_gate",
  "world_verdict_rewrite": {
    "previous_world_verdict": "not_verified",
    "rewritten_world_verdict": "verified",
    "ready_for_verified_outcome_ingestion_gate": true,
    "world_verdict_rewrite_output_only": true
  }
}
```

The ready output may be consumed only by a later verified outcome ingestion
gate. It is not durable state by itself.

## 5. Guardrails

G17 keeps these invariants explicit:

- `read_only=true`;
- `mutation_surface=output_only`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`;
- `queries_live_runtime=false`;
- `requires_ready_durable_outcome_record_write_evidence_review_preflight=true`;
- `requires_explicit_world_verdict_rewrite_decision=true`;
- `performs_world_verdict_rewrite_output=true`;
- `persists_world_verdict=false`;
- `durable_outcome_record_written=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `verified_outcome_ingestion_allowed=false`;
- `persists_outcome_record=false`.

## 6. Boundary

Accepted by this slice:

- validating a scoped explicit world-verdict rewrite decision;
- producing a bounded verified verdict output package;
- preserving lineage from G16 reviewed durable write evidence;
- keeping verdict rewrite output separate from ingestion and persistence.

Still not accepted:

- persisting the rewritten world verdict;
- durable outcome record writes;
- memory writes;
- #94 verified outcome ingestion;
- MCP registration or profile exposure;
- inferring rewrite solely from a ready G16 review.

## 7. Next Slice

The next safe slice is a verified outcome ingestion gate. It must consume the
bounded G17 package and still require its own explicit ingestion decision before
admitting any #94 verified outcome flow.
