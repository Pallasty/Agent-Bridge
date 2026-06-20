# Live Semantic World Runtime — Runtime Executor Verified Outcome Ingestion Gate

Date: 2026-06-20

Status: ACCEPTED_G18_VERIFIED_OUTCOME_INGESTION_GATE_OUTPUT_ONLY

## 1. Purpose

G18 adds the next narrow gate after G17:

```text
world-verdict rewrite gate
  -> verified outcome ingestion gate
  -> verified outcome admission gate
```

It answers one question:

> Has an explicit ingestion-gate decision accepted the bounded G17
> `verified` world-verdict package as ready for a separate admission gate?

This is still an output-only gate. It emits a bounded verified outcome
admission package, but it does not ingest #94 outcomes, persist the world
verdict, write durable outcome records, write memory, register MCP tools, or
query a live runtime.

## 2. Required Input

The source gate must be G17:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_world_verdict_rewrite_gate.v0`;
- `world_verdict_rewrite_gate_verdict=ready_for_verified_outcome_ingestion_gate`;
- `next_allowed_gate=verified_outcome_ingestion_gate`;
- `ready_for_verified_outcome_ingestion_gate=true`;
- `previous_world_verdict=not_verified`;
- `rewritten_world_verdict=verified`;
- `world_verdict_rewrite_output_only=true`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  allowed by the source.

The explicit ingestion decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_decision.v0
```

Required decision properties:

- `decision_kind=verified_outcome_ingestion`;
- `decision=admit_verified_outcome_package`;
- `source_world_verdict=verified`;
- `reviewed_world_verdict_rewrite_gate_verdict=ready_for_verified_outcome_ingestion_gate`;
- `bounded_verified_verdict_package_present=true`;
- `verified_outcome_claim_present=true`;
- `world_verdict_rewrite_output_only_confirmed=true`;
- `reviewer_attestation_present=true`;
- `evidence_lineage_preserved=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `verified_outcome_ingestion_allowed=true`;
- `store_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `memory_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

## 3. Scope Matching

The ingestion decision must exactly match the G17 rewrite scope for:

- rewrite-decision id;
- source review-decision id;
- write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the gate.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_gate.v0",
  "verified_outcome_ingestion_gate_verdict": "ready_for_verified_outcome_admission",
  "status": "ready",
  "reason": "verified_outcome_ingestion_gate_ready_for_verified_outcome_admission",
  "next_allowed_gate": "verified_outcome_admission_gate",
  "verified_outcome_ingestion_gate": {
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "ready_for_verified_outcome_admission": true,
    "verified_outcome_admission_package_emitted_by_this_tool": true,
    "verified_outcome_ingested_by_this_tool": false,
    "world_verdict_persisted_by_this_tool": false,
    "durable_outcome_record_written_by_this_tool": false,
    "store_write_allowed": false,
    "memory_write_allowed": false,
    "outcome_ingestion_allowed": false
  }
}
```

## 5. Boundary

G18 does not perform ingestion. It only turns a ready G17 rewrite package plus
an explicit ingestion-gate decision into a bounded package for the later
verified-outcome admission slice.

The critical distinction is:

- `verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_admission`:
  the next admission gate may consume the package;
- `verified_outcome_admission_package_emitted_by_this_tool=true`: this tool emitted a
  package, not durable state;
- `verified_outcome_ingested_by_this_tool=false`: no verified outcome was
  ingested here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome admission gate. It must consume the
G18 package and require its own admission decision before any durable #94
ingestion behavior is considered.
