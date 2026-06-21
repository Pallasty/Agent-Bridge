# Live Semantic World Runtime — Runtime Executor Verified Outcome Ingestion Execution Preflight

Date: 2026-06-20

Status: ACCEPTED_G19_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_OUTPUT_ONLY / G29_ACCEPTS_VERIFIED_OUTCOME_INGESTION_ADMISSION_PREFLIGHT_SOURCE

## 1. Purpose

G19 adds the next narrow preflight after G18:

```text
verified outcome ingestion gate
  -> verified outcome admission gate package
  -> verified outcome ingestion execution preflight
  -> verified outcome ingestion execution commit
```

It answers one question:

> Has an explicit execution decision accepted the bounded G18 package as ready
> for a separate commit/execution step?

G29 keeps that boundary but broadens the accepted source package. The preflight
may now consume either:

- the original G18 verified outcome ingestion gate package; or
- the later G28 verified outcome ingestion admission preflight package.

The G28 source is preferred when available because it carries the write-evidence,
store-write, persistence, writer, apply, commit, and admission lineage that the
execution decision must preserve before the next commit gate.

This remains output-only. It emits a bounded commit-ready package, but it does
not ingest #94 outcomes, persist the world verdict, write durable outcome
records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source package must be one of the accepted output-only packages below.

G18 source:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_gate.v0`;
- `verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_admission`;
- `next_allowed_gate=verified_outcome_admission_gate`;
- `ready_for_verified_outcome_admission=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_admission_package_emitted_by_this_tool=true`;
- `verified_outcome_ingestion_gate_output_only=true`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  allowed by the source.

G28 source:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight.v0`;
- `verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `next_allowed_gate=verified_outcome_ingestion_execution`;
- `ready_for_verified_outcome_ingestion_execution=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- admission, store-write, persistence, writer, apply, commit, source execution,
  source ingestion, rewrite, review, write-evidence, world, branch, generation,
  patch, outcome, idempotency, destination, key, digest, persisted-key, and
  persisted-digest lineage present;
- no admission, store-write, ingestion, world-verdict persistence, durable
  outcome-record write, memory, store, or MCP surface allowed by the source.

The explicit execution decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_decision.v0
```

Required decision properties:

- `decision_kind=verified_outcome_ingestion_execution`;
- `decision=approved_for_verified_outcome_ingestion_execution_preflight`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_verified_outcome_ingestion_gate_verdict=ready_for_verified_outcome_admission`;
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

For a G28 source, the decision must also use
`source_verified_outcome_ingestion_admission_scope`, review
`ready_for_verified_outcome_ingestion_execution`, and confirm:

- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`.

## 3. Scope Matching

For a G18 source, the execution decision must exactly match the ingestion gate
scope for:

- ingestion-decision id;
- source rewrite-decision id;
- source review-decision id;
- write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the preflight.

For a G28 source, the execution decision must exactly match the admission
preflight scope for:

- admission-decision id;
- write-evidence review decision id;
- write-evidence id;
- store-write execution id;
- persistence decision and source execution ids;
- writer, apply, commit, source execution, source ingestion, source rewrite,
  source review, and source write-evidence ids;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

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

When the source is G28, ready output additionally carries the admission lineage:

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `source_admission_decision_id`;
- `source_write_evidence_review_decision_id`;
- store-write, persistence, writer, apply, commit, source execution, and source
  write-evidence ids;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`;
- `source_verified_outcome_ingestion_admission_preflight`.

## 5. Boundary

G19/G29 does not execute ingestion. It only turns a ready G18 or G28 package
plus an explicit execution decision into a bounded package for a later
commit/execution slice.

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
