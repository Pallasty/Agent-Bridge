# Live Semantic World Runtime - Interaction Feedback Runtime Executor Operator Submission Token Preflight

**2026-06-16 - status: ACCEPTED_G2_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_ONLY**

Parent documents:

- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback runtime executor authority gates](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_AUTHORITY_GATES_2026_06_16.md)
- [Interaction feedback runtime executor authority gates acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_AUTHORITY_GATES_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor live lookup preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_2026_06_16.md)
- [Interaction feedback runtime executor live lookup preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor operator submission token preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_ACCEPTANCE_2026_06_16.md)

Forum anchors:

- `#102` post `#2437`: G2 operator submission token design/preflight claim.
- `#102` post `#3191`: G2 acceptance closeout claim and verification summary.

## 0. Purpose

This slice implements the second runtime executor authority gate:

```text
agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0
```

It consumes an accepted G1 live lookup preflight and an explicit operator
decision payload:

```text
G1 live lookup preflight + operator decision -> G2 operator submission token preflight
```

The helper validates that the operator approval is explicit, scoped to the G1
lookup evidence, expiring, and replay-guarded. It emits a token candidate for
G3 patch-application review.

It does not persist the token, submit an apply request, apply a patch, verify
post-apply results, ingest outcomes, expose an MCP tool, write store or memory,
call #94 ingestion, or rewrite the source world verdict.

## 1. Input Contract

Accepted inputs:

- a wrapper with `lookup_preflight` and `operator_decision`;
- a wrapper with `runtime_executor_live_lookup_preflight` and
  `operator_submission_decision`;
- a direct G1 live lookup preflight, which blocks because the operator decision
  is missing.

The G1 preflight must be:

- `agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0`;
- `lookup_preflight_verdict=ready_for_operator_submission_review`;
- `source_world_verdict=not_verified`;
- `lookup_evidence.ready_for_operator_submission_review=true`;
- still non-authoritative for executor submission, patch application,
  verification, outcome ingestion, store, memory, and MCP exposure.

The operator decision must be:

- `agent_bridge.lswr.runtime_executor.operator_submission_decision.v0`;
- `decision=approved`;
- `requested_authority=operator_submission_token_only`;
- carrying `operator_id`, `decision_id`, `approved_at`, and `expires_at`;
- scoped to the exact G1 `lookup_evidence_id`, world, branch,
  `runtime_generation`, patch, and apply request;
- explicitly non-mutating: no submission, application, verification, ingestion,
  or state write flags may be true.

## 2. Output Shape

Blocked without an explicit operator decision:

```json
{
  "submission_token_preflight_verdict": "blocked",
  "reason": "explicit_operator_submission_decision_required",
  "operator_submission_token": {
    "token_id": null,
    "token_candidate_emitted_by_this_tool": false,
    "ready_for_patch_application_gate_review": false,
    "ready_for_executor_submission": false,
    "apply_request_submitted": false,
    "patch_application_performed": false
  }
}
```

Ready with an explicit matching operator decision:

```json
{
  "submission_token_preflight_verdict": "ready_for_patch_application_gate_review",
  "reason": "operator_submission_token_preflight_ready_for_patch_application_gate_review",
  "operator_submission_token": {
    "token_id": "submit_patch_arrival_bath_move_002",
    "token_type": "operator_submission_gate_token",
    "operator_id": "human:owner",
    "lookup_evidence_id": "live_lookup_arrival_bath_move_002",
    "runtime_generation": "runtime_gen_1284",
    "patch_id": "patch_arrival_bath_move_002",
    "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002",
    "token_candidate_emitted_by_this_tool": true,
    "submission_token_persisted": false,
    "ready_for_patch_application_gate_review": true,
    "ready_for_executor_submission": false,
    "apply_request_submitted": false,
    "patch_application_performed": false,
    "verification_performed": false,
    "outcome_ingestion_allowed": false
  }
}
```

## 3. Guardrails

The implementation keeps:

- `read_only=true`;
- `mutation_surface=none`;
- `requires_ready_live_lookup_preflight=true`;
- `requires_explicit_operator_decision=true`;
- `operator_authority_scope=operator_submission_token_only`;
- `submits_apply_request=false`;
- `applies_patch=false`;
- `verifies_post_apply_result=false`;
- `outcome_ingestion_allowed=false`;
- `persists_submission_token=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

## 4. Implementation Artifacts

Code:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke.rs`

Verifier:

- `scripts/verify-biocortex-retrieval-shadow.sh`

## 5. Verification

Targeted tests:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_operator_submission_token_preflight -- --nocapture
```

Smoke paths:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke -- --format json --assert-blocked-without-operator-decision --assert-read-only
```

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke -- --with-operator-decision --format json --assert-ready-for-patch-application-gate-review --assert-read-only
```

Full verifier:

```text
AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs scripts/verify-biocortex-retrieval-shadow.sh
```

## 6. Non-Goals

Still not accepted:

- MCP registration or profile exposure;
- live runtime connector implementation;
- token persistence;
- executor queue submission;
- apply-request submission;
- patch application;
- Onsen mutation;
- post-apply verification execution;
- outcome ingestion;
- store or memory writes;
- #94 ingestion;
- verification verdict rewrite.

## 7. Acceptance And Next Slice

This G2 read-only token-candidate preflight is accepted by
[runtime executor operator submission token preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_ACCEPTANCE_2026_06_16.md).

G3 patch application gate preflight is now implemented pending acceptance:

- `docs/design/LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_2026_06_16.md`

It consumes this G2 token candidate without treating it as permission to mutate:
the G3 slice only validates a separate patch-application gate decision and
emits readiness for a later separate executor invocation.
