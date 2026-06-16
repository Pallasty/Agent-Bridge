# LSWR Interaction Feedback Runtime Executor Patch Application Gate Preflight Acceptance

**2026-06-16 - status: ACCEPTED_G3_PATCH_APPLICATION_GATE_PREFLIGHT_ONLY**

Parent documents:

- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback runtime executor authority gates](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_AUTHORITY_GATES_2026_06_16.md)
- [Interaction feedback runtime executor authority gates acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_AUTHORITY_GATES_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor live lookup preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor operator submission token preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor patch application gate preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_2026_06_16.md)

Forum anchors:

- `#102` post `#3195`: G3 patch-application design claim. This acceptance
  pivoted after `db71d73` landed a concrete G3 gate preflight on GitHub before
  the local design-only draft was committed.

Git anchors:

- G3 patch application gate preflight landed in `db71d73`.
- This acceptance reviewed local `master=db71d73`, with `github/master=db71d73`
  and `origin/master=7823336` before the acceptance docs-only follow-up.

## 0. Purpose

This acceptance records that the G3 runtime executor patch application gate
preflight is accepted as a read-only executor-invocation readiness boundary
only:

```text
agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0
```

The accepted surface consumes:

```text
accepted G2 operator submission token preflight
+ explicit patch application gate decision
```

and emits either:

- `patch_application_gate_preflight_verdict=blocked`; or
- `patch_application_gate_preflight_verdict=ready_for_separate_executor_invocation`.

It does not invoke the patch executor. It does not submit an apply request,
apply a patch, mutate Onsen, verify post-apply state, ingest outcomes, expose an
MCP tool, write store or memory, call #94 ingestion, or rewrite the source world
verdict.

## 1. Evidence Inspected

Code and test artifacts:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke.rs`

Design and verifier artifacts:

- G3 patch application gate preflight document;
- G2 operator submission token preflight acceptance;
- runtime executor authority-gate design and acceptance documents;
- `scripts/verify-biocortex-retrieval-shadow.sh` coverage references.

Behavior inspected:

- direct G2 preflight input blocks without an explicit patch-application gate
  decision;
- wrapper input with `submission_token_preflight` and
  `patch_application_gate_decision` is accepted only when both schemas and all
  guardrails match;
- source G2 preflight must still be
  `ready_for_patch_application_gate_review`;
- source world verdict must remain `not_verified`;
- source G2 token must be emitted but not persisted, not ready for direct
  executor submission, and not already submitted/applied/verified/ingested;
- gate decision must be explicit, approved, scoped to
  `patch_application_executor_invocation_gate_only`, expiring, replay-guarded,
  and bound to the exact G2 token id, token idempotency key, world, branch,
  runtime generation, patch, source apply request, and operator decision;
- ready output permits review of a separate executor invocation path, while the
  preflight itself keeps executor invocation, apply request submission, patch
  application, post-apply verification, outcome ingestion, store, memory, and
  MCP exposure disabled.

## 2. Verification

Passed:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_patch_application_gate_preflight -- --nocapture
```

Result:

```text
4 passed; 0 failed
```

Passed:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- --format json --assert-blocked-without-patch-application-gate-decision --assert-read-only
```

The blocked smoke confirmed:

- `reason=explicit_patch_application_gate_decision_required`;
- `patch_application_gate.ready_for_separate_patch_executor_invocation=false`;
- `separate_patch_executor_invocation_allowed_after_this_gate=false`;
- `executor_invocation_performed_by_this_tool=false`;
- `apply_request_submitted=false`;
- `patch_application_performed=false`;
- `verification_performed=false`;
- `outcome_ingestion_allowed=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

Passed:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- --with-patch-application-gate-decision --format json --assert-ready-for-separate-executor-invocation --assert-read-only
```

The ready smoke confirmed:

- `patch_application_gate_preflight_verdict=ready_for_separate_executor_invocation`;
- `reason=patch_application_gate_preflight_ready_for_separate_executor_invocation`;
- `patch_application_gate.gate_id=patch_application_gate_arrival_bath_move_002`;
- `gate_type=patch_application_executor_invocation_gate`;
- `gate_decision_id=patch_application_gate_decision_arrival_bath_move_002`;
- `operator_submission_token_id=submit_patch_arrival_bath_move_002`;
- `operator_submission_token_idempotency_key=patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002`;
- `idempotency_key=patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002`;
- `ready_for_separate_patch_executor_invocation=true`;
- `separate_patch_executor_invocation_allowed_after_this_gate=true`;
- `executor_invocation_performed_by_this_tool=false`;
- `apply_request_submitted=false`;
- `patch_application_performed=false`;
- `verification_performed=false`;
- `outcome_ingestion_allowed=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

Passed:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture -- --nocapture
```

Result:

```text
50 passed; 0 failed
```

Passed:

```text
cargo check -p ab-bridge --all-targets
```

Passed:

```text
git diff --check
```

Passed:

```text
bash -n scripts/verify-biocortex-retrieval-shadow.sh
```

Formatter note:

- `cargo fmt -p ab-bridge --check` was attempted after `db71d73`, but it fails
  on pre-existing E4 `crates/bridge/src/mcp_tools.rs` formatting outside this
  G3 preflight surface.
- This acceptance does not format or modify that E4 implementation code to
  avoid mixing the orthogonal outcome-admission writer line into the G3
  closeout.

Full verifier note:

- This local closeout did not rerun the full
  `scripts/verify-biocortex-retrieval-shadow.sh` path because
  `/Data/CascadeProjects/biocortex-rs` was absent in this environment.
- The acceptance here therefore relies on targeted Rust tests, the full
  interaction-feedback fixture suite, smoke examples, cargo check, shell syntax
  check, and merged verifier coverage rather than claiming a fresh
  full-verifier pass from this workstation.

## 3. Boundary Review

Accepted behavior:

- require accepted G2 operator submission token preflight evidence;
- require an explicit patch-application gate decision;
- scope the decision to
  `patch_application_executor_invocation_gate_only`;
- bind the decision to the exact G2 token, token idempotency key, world,
  branch, runtime generation, patch, source apply request, and operator
  decision;
- preserve expiry and replay guard fields for the next gate;
- emit only a readiness decision for a separate patch executor invocation path;
- keep executor invocation, apply request submission, patch application,
  post-apply verification, and outcome ingestion disabled in this tool.

Rejected behavior:

- infer or synthesize patch-application approval;
- persist a submission token;
- invoke a patch executor;
- submit an apply request;
- place work on an executor queue;
- apply a semantic patch;
- mutate Onsen or any live world;
- execute post-apply verification;
- ingest outcomes;
- write store or memory;
- call #94 ingestion;
- register or expose an MCP tool;
- rewrite the source world verdict.

## 4. Acceptance Matrix

| Gate | Result | Evidence |
|---|---|---|
| G3-A: Explicit gate decision required | `PASS` | Direct G2 input blocks with `explicit_patch_application_gate_decision_required`. |
| G3-B: Source G2 evidence must stay inert | `PASS` | Source token must remain emitted-only, not persisted/submitted/applied/verified/ingested. |
| G3-C: Decision scope is invocation-gate-only | `PASS` | Accepted decision requires `requested_authority=patch_application_executor_invocation_gate_only`. |
| G3-D: Runtime and token scope match | `PASS` | Token id, token idempotency key, world, branch, generation, patch, apply request, and operator decision are checked. |
| G3-E: No invocation or submission | `PASS` | Ready path keeps `executor_invocation_performed_by_this_tool=false` and `apply_request_submitted=false`. |
| G3-F: No mutation or ingestion | `PASS` | Ready path keeps patch application, verification, outcome ingestion, store, memory, and MCP flags false. |

## 5. Decision

Decision: `ACCEPTED_G3_PATCH_APPLICATION_GATE_PREFLIGHT_ONLY`.

Accepted:

- `agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0`;
- `agent_bridge.lswr.runtime_executor.patch_application_gate_decision.v0`;
- `build_interaction_feedback_runtime_executor_patch_application_gate_preflight(...)`;
- `render_interaction_feedback_runtime_executor_patch_application_gate_preflight(...)`;
- stdout-only smoke example;
- tests proving blocked-without-decision, explicit-decision-ready,
  bad-decision-blocked, and required-submission-input behavior;
- verifier coverage for blocked and ready smoke paths.

Still not accepted:

- MCP registration;
- default-profile or Codex-essential exposure;
- actual live runtime connector;
- token persistence;
- executor invocation implementation;
- executor queue submission;
- apply-request submission;
- patch application;
- Onsen mutation;
- post-apply verification execution;
- outcome ingestion;
- store access;
- memory writes;
- #94 ingestion;
- verification verdict rewrite.

## 6. Next Slice

The next safe slice is separate patch executor invocation design.

That slice must consume the accepted G3 readiness packet without treating it as
proof that invocation, application, verification, ingestion, or verdict rewrite
already happened. The invocation path must still distinguish executor
invocation, runtime application evidence, G4 post-apply verification, and G5
outcome ingestion.
