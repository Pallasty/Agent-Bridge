# LSWR Interaction Feedback Runtime Executor Patch Executor Invocation Preflight

Status: ACCEPTED_G4_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_ONLY / read-only G4

Date: 2026-06-16

Parent documents:

- [Runtime executor patch application gate preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_2026_06_16.md)
- [Runtime executor patch application gate preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_ACCEPTANCE_2026_06_16.md)
- [Runtime executor patch executor invocation preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_ACCEPTANCE_2026_06_16.md)

Forum anchors:

- `#102` post `#3199`: G4 patch executor invocation preflight claim.

## 1. Purpose

G4 consumes the accepted G3 patch-application gate preflight and an explicit
patch executor invocation decision. It answers one narrow question:

> Is this exact scoped G3 gate ready to emit a reviewable separate patch
> executor invocation request envelope?

It may emit an invocation request envelope to stdout. It does not invoke the
executor, submit work to an executor queue, submit an apply request, apply a
patch, verify post-apply state, ingest outcomes, or write any durable state.

## 2. Input Contract

Accepted inputs:

- a G3
  `agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0`;
- a wrapper containing that preflight plus
  `patch_executor_invocation_decision`;
- an invocation decision with schema
  `agent_bridge.lswr.runtime_executor.patch_executor_invocation_decision.v0`.

The source G3 preflight must be:

- `patch_application_gate_preflight_verdict=ready_for_separate_executor_invocation`;
- `source_world_verdict=not_verified`;
- `ready_for_separate_patch_executor_invocation=true`;
- non-mutating:
  - `executor_invocation_performed_by_this_tool=false`;
  - `apply_request_submitted=false`;
  - `patch_application_performed=false`;
  - `verification_performed=false`;
  - `outcome_ingestion_allowed=false`.

The invocation decision must be:

- `decision=approved`;
- `requested_authority=separate_patch_executor_invocation_only`;
- `separate_patch_executor_invocation_allowed=true`;
- scoped to the G3 gate id, gate decision id, gate idempotency key,
  operator-submission token id, world, branch, runtime generation, patch id,
  and source apply request id;
- non-mutating:
  - `executor_invocation_performed=false`;
  - `executor_queue_submission_performed=false`;
  - `apply_request_submitted=false`;
  - `patch_application_performed=false`;
  - `verification_allowed=false`;
  - `outcome_ingestion_allowed=false`;
  - `writes_state=false`.

## 3. Output Shape

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_executor_invocation_preflight.v0",
  "patch_executor_invocation_preflight_verdict": "ready_for_separate_patch_executor_invocation_request",
  "reason": "patch_executor_invocation_preflight_ready_for_invocation_request",
  "patch_executor_invocation_request": {
    "request_id": "patch_executor_invocation_arrival_bath_move_002",
    "target_executor": "separate_lswr_patch_executor",
    "request_type": "patch_executor_invocation_request",
    "patch_application_gate_id": "patch_application_gate_arrival_bath_move_002",
    "invocation_decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
    "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/patch_application_gate_arrival_bath_move_002/patch_executor_invocation_decision_arrival_bath_move_002",
    "ready_for_separate_patch_executor_invocation_request": true,
    "invocation_request_emitted_by_this_tool": true,
    "executor_invocation_performed_by_this_tool": false,
    "executor_queue_submission_performed": false,
    "apply_request_submitted": false,
    "patch_application_performed": false,
    "verification_performed": false,
    "outcome_ingestion_allowed": false
  },
  "next_allowed_gate": "separate_patch_executor_runtime_application_evidence"
}
```

Blocked output without the explicit invocation decision:

```json
{
  "patch_executor_invocation_preflight_verdict": "blocked",
  "reason": "explicit_patch_executor_invocation_decision_required",
  "next_allowed_gate": "repair_patch_executor_invocation_input"
}
```

## 4. Guardrails

The implementation keeps:

- `read_only=true`;
- `mutation_surface=none`;
- `requires_ready_patch_application_gate_preflight=true`;
- `requires_explicit_patch_executor_invocation_decision=true`;
- `patch_executor_invocation_authority_scope=separate_patch_executor_invocation_only`;
- `invokes_patch_executor=false`;
- `submits_executor_queue=false`;
- `submits_apply_request=false`;
- `applies_patch=false`;
- `verifies_post_apply_result=false`;
- `outcome_ingestion_allowed=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

`invocation_request_emitted_by_this_tool=true` means only that the pure builder
returned a reviewable envelope. It must not be interpreted as queue submission
or runtime execution.

## 5. Implementation Artifacts

Code:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke.rs`

Verifier:

- `scripts/verify-biocortex-retrieval-shadow.sh`

## 6. Verification

Targeted tests:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_patch_executor_invocation_preflight -- --nocapture
```

Smoke paths:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke -- --format json --assert-blocked-without-patch-executor-invocation-decision --assert-read-only
```

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke -- --with-patch-executor-invocation-decision --format json --assert-ready-for-separate-patch-executor-invocation-request --assert-read-only
```

Full verifier:

```text
AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs scripts/verify-biocortex-retrieval-shadow.sh
```

## 7. Non-Goals

Still not accepted:

- MCP registration or profile exposure;
- live runtime connector implementation;
- token persistence;
- executor invocation;
- executor queue submission;
- apply-request submission;
- patch application;
- Onsen mutation;
- post-apply verification execution;
- outcome ingestion;
- store or memory writes;
- #94 ingestion;
- verification verdict rewrite.

## 8. Next Slice

The next safe slice is separate patch executor runtime application evidence.
It must consume an invocation request envelope without assuming the executor
was invoked, the patch was applied, or postconditions were verified.
