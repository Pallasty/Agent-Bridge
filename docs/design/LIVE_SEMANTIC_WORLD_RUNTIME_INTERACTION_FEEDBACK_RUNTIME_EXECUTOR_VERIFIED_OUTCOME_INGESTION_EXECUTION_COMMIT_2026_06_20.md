# Live Semantic World Runtime — Runtime Executor Verified Outcome Ingestion Execution Commit

Date: 2026-06-20

Status: Draft implementation spec / G30_ACCEPTS_ADMISSION_SOURCE_EXECUTION_PREFLIGHT

## 1. Purpose

G20 adds the next narrow gate after G19:

```text
verified outcome ingestion execution preflight
  -> verified outcome ingestion execution commit
  -> verified outcome ingestion apply
```

It answers one question:

> Has an explicit commit decision accepted the bounded G19 package as ready
> for a separate verified outcome ingestion apply step?

G30 keeps the output-only boundary while preserving the G29 admission-source
lineage carried inside the G19 execution preflight. When the source preflight was
built from a G28 verified outcome ingestion admission preflight, the commit gate
must keep that admission, write-evidence, store-write, persistence, writer,
apply, commit, and source execution lineage intact before it emits an apply-ready
package.

This remains output-only. It emits a bounded apply-ready package, but it does
not ingest #94 outcomes, persist the world verdict, write durable outcome
records, write memory, register MCP tools, or query a live runtime.

## 2. Required Input

The source preflight must be G19:

- schema `agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight.v0`;
- `verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`;
- `next_allowed_gate=verified_outcome_ingestion_execution_commit`;
- `ready_for_verified_outcome_ingestion_execution_commit=true`;
- `previous_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `verified_outcome_ingestion_execution_preflight_output_only=true`;
- no write, memory, ingestion, world-verdict persistence, store, or MCP surface
  allowed by the source.

The explicit commit decision must use:

```text
agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_commit_decision.v0
```

Required decision properties:

- `decision_kind=verified_outcome_ingestion_execution_commit`;
- `decision=approved_for_verified_outcome_ingestion_apply`;
- `source_world_verdict=not_verified`;
- `verified_world_verdict=verified`;
- `reviewed_verified_outcome_ingestion_execution_preflight_verdict=ready_for_verified_outcome_ingestion_execution_commit`;
- `execution_preflight_package_confirmed=true`;
- `verified_outcome_package_confirmed=true`;
- `reviewer_attestation_present=true`;
- `evidence_lineage_preserved=true`;
- `outcome_record_digest_confirmed=true`;
- `idempotency_key_confirmed=true`;
- `persisted_key_confirmed=true`;
- `persisted_digest_confirmed=true`;
- `apply_boundary_acknowledged=true`;
- `outcome_ingestion_allowed=false`;
- `memory_write_allowed=false`;
- `verified_outcome_ingested_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `world_verdict_persisted_by_this_tool=false`.

For a G29 admission-source execution preflight, the commit decision must also
confirm:

- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`.

## 3. Scope Matching

The commit decision must exactly match the G19 execution preflight scope for:

- execution-decision id;
- source ingestion, rewrite, and review decision ids;
- write-evidence id;
- world, branch, runtime generation, and patch ids;
- outcome candidate, schema, idempotency key, payload digest, destination,
  record key, record digest, persisted key, and persisted digest.

Any mismatch blocks the commit gate.

For a G29 admission-source execution preflight, the commit decision must also
match:

- source admission-decision id;
- source write-evidence review decision id;
- store-write execution id;
- persistence decision and source execution ids;
- writer, apply, source commit, source prior execution, and source
  write-evidence ids.

## 4. Ready Output

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit.v0",
  "verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
  "status": "ready",
  "reason": "verified_outcome_ingestion_execution_commit_ready_for_apply",
  "next_allowed_gate": "verified_outcome_ingestion_apply",
  "verified_outcome_ingestion_execution_commit": {
    "previous_world_verdict": "not_verified",
    "verified_world_verdict": "verified",
    "ready_for_verified_outcome_ingestion_apply": true,
    "verified_outcome_ingestion_execution_commit_output_only": true,
    "verified_outcome_ingested_by_this_tool": false,
    "world_verdict_persisted_by_this_tool": false,
    "durable_outcome_record_written_by_this_tool": false,
    "memory_write_allowed": false,
    "outcome_ingestion_allowed": false
  }
}
```

When the source is a G29 admission-source execution preflight, ready output also
carries:

- `source_verified_outcome_ingestion_admission_preflight_verdict=ready_for_verified_outcome_ingestion_execution`;
- `source_admission_decision_id`;
- `source_write_evidence_review_decision_id`;
- store-write, persistence, writer, apply, source commit, source prior
  execution, and source write-evidence ids;
- `admission_preflight_confirmed=true`;
- `admission_decision_confirmed=true`.

## 5. Boundary

G20/G30 does not execute verified outcome ingestion. It only turns a ready G19
package plus an explicit commit decision into a bounded package for a later
apply slice, preserving admission-source lineage when present.

The critical distinction is:

- `verified_outcome_ingestion_execution_commit_verdict=ready_for_verified_outcome_ingestion_apply`:
  the next apply step may consume the package;
- `ready_for_verified_outcome_ingestion_apply=true`: the commit gate is
  satisfied;
- `verified_outcome_ingested_by_this_tool=false`: no ingestion happened here;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 6. Next Slice

The next safe slice is verified outcome ingestion apply. It must consume the
G20 package and require its own apply decision before any durable #94 ingestion
behavior is considered.
