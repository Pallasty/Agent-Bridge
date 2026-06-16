# Live Semantic World Runtime - Interaction Feedback Patch Apply Request Boundary Acceptance

**2026-06-16 - role: acceptance review / apply-request-only**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback semantic patch draft](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_2026_06_15.md)
- [Interaction feedback patch execution preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_2026_06_15.md)
- [Interaction feedback patch execution preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback patch apply request boundary](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_BOUNDARY_2026_06_15.md)

## 0. Purpose

This review accepts the landed patch apply request boundary as an
apply-request-only surface. It may package a ready patch execution preflight
into an external executor request envelope, but it does not approve submitting
that request, live runtime lookup, patch application, Onsen mutation, outcome
ingestion, MCP registration, store access, memory writes, #94 ingestion, or
verification verdict rewrite.

## 1. Evidence Inspected

Implemented surface:

```text
agent_bridge.lswr.interaction_feedback_patch_apply_request.v0
```

Code artifacts:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_patch_apply_request_smoke.rs`

Doc artifact:

- `LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_BOUNDARY_2026_06_15.md`

## 2. Verification

Current verification evidence:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_patch_apply_request -- --nocapture
```

Passed: 4 targeted tests.

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- --format json --assert-blocked-without-ready-preflight --assert-read-only
```

Passed. The blocked path preserves:

- `source_preflight_verdict=blocked`;
- `source_world_verdict=not_verified`;
- `apply_request_verdict=blocked`;
- `reason=source_preflight_not_ready`;
- `ready_for_external_submission=false`;
- `request_id=null`;
- `target_runtime=null`;
- `patch=null`;
- `apply_performed=false`;
- `submitted_by_this_tool=false`;
- `outcome_ingestion_allowed_by_this_tool=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`.

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- --with-fixture-context --format json --assert-ready-with-context --assert-read-only
```

Passed. The ready path preserves:

- `source_preflight_verdict=ready_for_execution_request`;
- `source_world_verdict=not_verified`;
- `apply_request_verdict=ready_for_external_executor`;
- `reason=external_apply_request_ready`;
- `apply_request.request_id=apply_request_arrival_bath_move_002`;
- `apply_request.target_runtime.executor=separate_lswr_patch_executor`;
- `apply_request.patch.patch_id=patch_arrival_bath_move_002`;
- `apply_request.patch.args.cell=[5, 2]`;
- required citations `[verify_patch_arrival_bath_move_001, fb_arrival_crowded_001]`;
- `ready_for_external_submission=true`;
- `requires_operator_gate=true`;
- `requires_external_executor=true`;
- `apply_performed=false`;
- `submitted_by_this_tool=false`;
- `outcome_ingestion_allowed_by_this_tool=false`.

```text
AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs scripts/verify-biocortex-retrieval-shadow.sh
```

Passed with the blocked-without-ready-preflight and ready-with-explicit-context
apply-request smoke paths in the full verifier.

## 3. Boundary Review

Accepted behavior:

- consume only an explicit patch execution preflight, or a wrapper containing
  that explicit preflight;
- block raw fixtures, reports, plans, drafts, or any implicit normalization path;
- reject preflights that are not ready, lack resolved args, lack citations, or
  claim execution/apply authority;
- package a ready preflight as an external executor request envelope;
- preserve required citations, `source_world_verdict=not_verified`, and
  post-apply verification preconditions;
- remain module/test/example only.

Rejected behavior:

- build a preflight behind the caller's back;
- query a live LSWR runtime;
- submit the apply request;
- execute or apply the patch;
- mutate Onsen or any live world;
- ingest outcomes;
- call store, memory, or #94 ingestion APIs;
- register a new MCP tool;
- expose the surface in default or Codex-essential profiles;
- turn a failed source verdict into `verified`.

## 4. Acceptance Matrix

| Gate | Result | Evidence |
|---|---|---|
| A1: Ready preflight required | `PASS` | Blocked preflight yields `source_preflight_not_ready`. |
| A2: No implicit normalization | `PASS` | Draft input yields `patch_execution_preflight_required`. |
| A3: External executor only | `PASS` | Ready output keeps `submitted_by_this_tool=false` and `apply_performed=false`. |
| A4: No authority laundering | `PASS` | Tampered execution/apply guardrails block the request. |
| A5: Preserve verification posture | `PASS` | Ready and blocked paths keep `source_world_verdict=not_verified` and citations. |

## 5. Decision

Decision: `ACCEPTED_APPLY_REQUEST_ONLY`.

Accepted:

- `agent_bridge.lswr.interaction_feedback_patch_apply_request.v0`;
- `build_interaction_feedback_patch_apply_request(...)`;
- `render_interaction_feedback_patch_apply_request(...)`;
- stdout-only smoke example;
- tests proving blocked-without-ready-preflight, ready-with-explicit-context,
  draft-input blocked, and tampered-preflight blocked paths;
- full verifier coverage for blocked and ready smoke paths.

Still not accepted:

- MCP registration;
- default-profile or Codex-essential exposure;
- live runtime lookup by this surface;
- apply request submission;
- patch application;
- Onsen mutation;
- outcome ingestion;
- store access;
- memory writes;
- #94 ingestion;
- verification verdict rewrite.

## 6. Next Slice

The next safe slice is a separate runtime executor design preflight. It should
consume an accepted apply-request envelope but still block before any live LSWR
lookup, request submission, patch application, or outcome ingestion until those
authority boundaries are reviewed independently.

Follow-up design preflight:

- [Interaction feedback runtime executor design preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_2026_06_16.md)
