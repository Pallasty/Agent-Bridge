# LSWR Interaction Feedback Runtime Executor Durable Outcome-Ingestion Gate Preflight

Status: ACCEPTED_G8_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_ONLY / read-only G8

Date: 2026-06-18

Parent documents:

- [Runtime executor outcome-ingestion review preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_2026_06_18.md)
- [Runtime executor outcome-ingestion review preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_ACCEPTANCE_2026_06_18.md)
- [Runtime executor durable outcome-ingestion gate preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_ACCEPTANCE_2026_06_18.md)

Forum anchors:

- `#102` post `#3321`: G8 durable outcome-ingestion gate preflight claim.

## 1. Purpose

G8 consumes the accepted G7 outcome-ingestion review preflight and an explicit
durable outcome-ingestion gate decision. It answers one narrow question:

> Is the reviewed outcome scoped, idempotent, and complete enough to proceed to
> a later durable outcome-ingestion execution step?

It does not ingest outcomes, persist outcome records, write memory/store rows,
expose MCP, or rewrite the world verdict.

## 2. Input Contract

Accepted inputs:

- a G7
  `agent_bridge.lswr.interaction_feedback_runtime_executor_outcome_ingestion_review_preflight.v0`;
- a wrapper containing that preflight plus
  `durable_outcome_ingestion_gate_decision`;
- a gate decision packet with schema
  `agent_bridge.lswr.runtime_executor.durable_outcome_ingestion_gate_decision.v0`.

The source G7 preflight must be:

- `outcome_ingestion_review_preflight_verdict=ready_for_durable_ingestion_gate`;
- `source_world_verdict=not_verified`;
- `outcome_ingestion_review.decision=approved_for_durable_ingestion_gate`;
- `outcome_ingestion_review.ready_for_durable_ingestion_gate=true`;
- explicit that this tool has not ingested, persisted, or rewritten.

The gate decision must:

- use `gate_kind=durable_outcome_ingestion_gate`;
- set `decision=approved_for_durable_ingestion_execution`;
- scope to the exact G7 review id, verification id, runtime application
  evidence id, invocation request id, world, branch, runtime generation, and
  patch id;
- preserve `source_world_verdict=not_verified`;
- confirm `reviewed_ingestion_review_decision=approved_for_durable_ingestion_gate`;
- provide an `outcome_record_candidate_id`;
- provide an `outcome_record_schema`;
- provide an `idempotency_key`;
- set `outcome_payload_complete=true`;
- keep later surfaces disabled:
  - `durable_ingestion_execution_allowed=false`;
  - `world_verdict_rewrite_allowed=false`;
  - `outcome_record_persisted=false`.

## 3. Output Shape

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight.v0",
  "durable_outcome_ingestion_gate_preflight_verdict": "ready_for_durable_outcome_ingestion_execution",
  "reason": "durable_outcome_ingestion_gate_preflight_ready_for_execution",
  "durable_outcome_ingestion_gate": {
    "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
    "review_id": "outcome_ingestion_review_arrival_bath_move_002",
    "decision": "approved_for_durable_ingestion_execution",
    "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
    "outcome_payload_complete": true,
    "ready_for_durable_outcome_ingestion_execution": true,
    "durable_outcome_ingestion_gate_performed_by_this_tool": false,
    "durable_ingestion_execution_allowed": false,
    "world_verdict_rewrite_allowed": false,
    "outcome_record_persisted_by_this_tool": false
  },
  "next_allowed_gate": "durable_outcome_ingestion_execution"
}
```

Blocked output without explicit gate decision:

```json
{
  "durable_outcome_ingestion_gate_preflight_verdict": "blocked",
  "reason": "explicit_durable_outcome_ingestion_gate_decision_required",
  "next_allowed_gate": "repair_durable_outcome_ingestion_gate_input"
}
```

## 4. Guardrails

The implementation keeps:

- `read_only=true`;
- `mutation_surface=none`;
- `requires_ready_outcome_ingestion_review_preflight=true`;
- `requires_explicit_durable_outcome_ingestion_gate_decision=true`;
- `gate_kind=durable_outcome_ingestion_gate`;
- `performs_durable_outcome_ingestion_gate=false`;
- `durable_ingestion_execution_allowed=false`;
- `persists_outcome_record=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`;
- `feedback_changes_world_verdict_allowed=false`.

## 5. Non-Goals

Still not accepted:

- durable outcome-ingestion execution;
- store or memory writes;
- #94 ingestion;
- MCP registration or profile exposure;
- world verdict rewrite;
- treating a gate decision as a persisted outcome record;
- treating outcome ingestion as permission to rewrite world verdict.

## 6. Next Slice

The next safe slice is durable outcome-ingestion execution preflight. It must
consume G8 gate output without writing durable state unless a separate execution
implementation is accepted, and it must keep world-verdict rewrite behind a
later explicit gate.
