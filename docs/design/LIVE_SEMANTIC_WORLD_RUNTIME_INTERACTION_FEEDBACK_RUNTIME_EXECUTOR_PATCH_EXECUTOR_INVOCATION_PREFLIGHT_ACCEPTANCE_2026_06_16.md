# LSWR Interaction Feedback Runtime Executor Patch Executor Invocation Preflight Acceptance

Status: ACCEPTED_G4_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_ONLY

Date: 2026-06-16

Accepted document:

- [Runtime executor patch executor invocation preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_2026_06_16.md)

Forum anchors:

- `#102` post `#3199`: G4 patch executor invocation preflight claim.

## 1. Decision

Decision: `ACCEPTED_G4_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_ONLY`.

Accepted:

- `agent_bridge.lswr.interaction_feedback_runtime_executor_patch_executor_invocation_preflight.v0`;
- `agent_bridge.lswr.runtime_executor.patch_executor_invocation_decision.v0`;
- `build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(...)`;
- `render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(...)`;
- stdout-only smoke example;
- tests proving blocked-without-decision, explicit-decision-ready,
  bad-decision-blocked, and required-G3-input behavior;
- documentation linking the accepted G3 gate to this G4 preflight.

Still not accepted:

- MCP registration;
- default-profile or Codex-essential exposure;
- actual live runtime connector;
- token persistence;
- executor invocation;
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

## 2. Acceptance Evidence

Targeted G4 fixture tests:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_patch_executor_invocation_preflight -- --nocapture
```

Result:

- 4/4 passed.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke -- --format json --assert-blocked-without-patch-executor-invocation-decision --assert-read-only
```

Observed:

- `patch_executor_invocation_preflight_verdict=blocked`;
- `reason=explicit_patch_executor_invocation_decision_required`;
- `ready_for_separate_patch_executor_invocation_request=false`;
- `invocation_request_emitted_by_this_tool=false`;
- executor invocation, queue submission, apply request submission, patch
  application, verification, ingestion, store, memory, and MCP remain false.

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke -- --with-patch-executor-invocation-decision --format json --assert-ready-for-separate-patch-executor-invocation-request --assert-read-only
```

Observed:

- `patch_executor_invocation_preflight_verdict=ready_for_separate_patch_executor_invocation_request`;
- `reason=patch_executor_invocation_preflight_ready_for_invocation_request`;
- `request_id=patch_executor_invocation_arrival_bath_move_002`;
- `target_executor=separate_lswr_patch_executor`;
- `invocation_request_emitted_by_this_tool=true`;
- `executor_invocation_performed_by_this_tool=false`;
- `executor_queue_submission_performed=false`;
- `apply_request_submitted=false`;
- `patch_application_performed=false`;
- `verification_performed=false`;
- `outcome_ingestion_allowed=false`.

Full fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture -- --nocapture
```

Result:

- 54/54 passed.

Static checks:

```text
cargo check -p ab-bridge --all-targets
git diff --check
git diff --cached --check
bash -n scripts/verify-biocortex-retrieval-shadow.sh
```

Result:

- all passed;
- existing warnings remain in `ab-store` and `crates/bridge/src/mcp_tools.rs`.

## 3. Boundary

This accepted G4 preflight can emit a reviewable invocation request envelope.
It cannot submit that envelope to a queue and cannot treat the envelope as proof
that runtime application happened.

The critical distinction is:

- `invocation_request_emitted_by_this_tool=true`: a pure, reviewable envelope
  exists in the returned output;
- `executor_invocation_performed_by_this_tool=false`: no executor was invoked;
- `executor_queue_submission_performed=false`: no queue item was submitted.

## 4. Next Slice

The next safe slice is
[separate patch executor runtime application evidence preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_2026_06_18.md).

That slice must consume a G4 invocation request envelope without assuming
executor invocation or patch application occurred. It should introduce a
separate runtime evidence packet for what the executor claims happened, while
keeping post-apply verification and outcome ingestion behind later gates.
