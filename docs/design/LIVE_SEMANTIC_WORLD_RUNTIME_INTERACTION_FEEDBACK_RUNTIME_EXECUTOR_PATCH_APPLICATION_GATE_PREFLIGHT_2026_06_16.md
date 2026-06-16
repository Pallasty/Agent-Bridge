# LSWR Interaction Feedback Runtime Executor Patch Application Gate Preflight

Status: implemented pending acceptance / read-only G3

Date: 2026-06-16

## 1. Purpose

G3 consumes the G2 operator submission token preflight and an explicit patch
application gate decision. It answers one narrow question:

> Is this exact scoped token candidate ready for a separate patch application
> executor invocation to be considered?

It does not invoke the executor. It does not submit an apply request. It does
not apply a patch.

## 2. Input Contract

Accepted inputs:

- a G2
  `agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0`;
- a wrapper containing that preflight plus
  `patch_application_gate_decision`;
- a gate decision with schema
  `agent_bridge.lswr.runtime_executor.patch_application_gate_decision.v0`.

The source G2 preflight must be:

- `submission_token_preflight_verdict=ready_for_patch_application_gate_review`;
- `source_world_verdict=not_verified`;
- backed by an emitted token candidate;
- not persisted;
- not ready for direct executor submission;
- not submitted, applied, verified, or ingested.

The gate decision must be:

- `decision=approved`;
- `requested_authority=patch_application_executor_invocation_gate_only`;
- `separate_patch_executor_invocation_allowed=true`;
- scoped to the G2 token id, token idempotency key, world, branch,
  runtime generation, patch id, source apply request id, and operator
  submission decision id;
- non-mutating:
  - `executor_invocation_performed=false`;
  - `apply_request_submitted=false`;
  - `patch_application_performed=false`;
  - `verification_allowed=false`;
  - `outcome_ingestion_allowed=false`;
  - `writes_state=false`.

## 3. Output Shape

Ready output:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0",
  "patch_application_gate_preflight_verdict": "ready_for_separate_executor_invocation",
  "reason": "patch_application_gate_preflight_ready_for_separate_executor_invocation",
  "patch_application_gate": {
    "gate_id": "patch_application_gate_arrival_bath_move_002",
    "gate_type": "patch_application_executor_invocation_gate",
    "gate_decision_id": "patch_application_gate_decision_arrival_bath_move_002",
    "operator_submission_token_id": "submit_patch_arrival_bath_move_002",
    "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002",
    "ready_for_separate_patch_executor_invocation": true,
    "executor_invocation_performed_by_this_tool": false,
    "apply_request_submitted": false,
    "patch_application_performed": false,
    "verification_performed": false,
    "outcome_ingestion_allowed": false
  },
  "next_allowed_gate": "separate_patch_application_executor_invocation"
}
```

Blocked output without the explicit gate decision:

```json
{
  "patch_application_gate_preflight_verdict": "blocked",
  "reason": "explicit_patch_application_gate_decision_required",
  "next_allowed_gate": "repair_patch_application_gate_input"
}
```

## 4. Guardrails

The implementation keeps:

- `read_only=true`;
- `mutation_surface=none`;
- `requires_ready_operator_submission_token_preflight=true`;
- `requires_explicit_patch_application_gate_decision=true`;
- `patch_application_authority_scope=patch_application_executor_invocation_gate_only`;
- `invokes_patch_executor=false`;
- `submits_apply_request=false`;
- `applies_patch=false`;
- `verifies_post_apply_result=false`;
- `outcome_ingestion_allowed=false`;
- `persists_submission_token=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

## 5. Implementation Artifacts

Code:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke.rs`

Verifier:

- `scripts/verify-biocortex-retrieval-shadow.sh`

## 6. Verification

Targeted tests:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_patch_application_gate_preflight -- --nocapture
```

Smoke paths:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- --format json --assert-blocked-without-patch-application-gate-decision --assert-read-only
```

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- --with-patch-application-gate-decision --format json --assert-ready-for-separate-executor-invocation --assert-read-only
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

The next safe slice is acceptance review for this G3 gate preflight.

After acceptance, the executor invocation path must remain separate from this
preflight. It should consume the G3 readiness packet and still distinguish
between invoking a separate executor, observing application evidence, verifying
postconditions, and ingesting any outcome.
