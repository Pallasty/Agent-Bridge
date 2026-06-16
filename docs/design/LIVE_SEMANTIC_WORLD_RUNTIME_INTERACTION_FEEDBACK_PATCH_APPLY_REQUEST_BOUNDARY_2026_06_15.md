# Live Semantic World Runtime - Interaction Feedback Patch Apply Request Boundary

**2026-06-15 - role: read-only apply-request boundary / external executor handoff**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback semantic patch draft](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_2026_06_15.md)
- [Interaction feedback patch execution preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_2026_06_15.md)
- [Interaction feedback patch execution preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_ACCEPTANCE_2026_06_15.md)

Forum anchors:
- `#102` post `#2422`: preflight verifier wiring completion and next safe slice.

## 0. Purpose

This slice adds one boundary after the accepted patch execution preflight:

```text
fixture / packet / report
  -> next-revision plan
  -> semantic patch draft
  -> patch execution preflight
  -> patch apply request boundary
```

The boundary answers one narrow question: is the ready preflight safe to package
as a request for a separate LSWR patch executor?

It does not normalize raw fixtures or drafts, query live runtime state, submit
an apply request, apply the patch, mutate Onsen, ingest outcomes, write
memory/store rows, register MCP tools, or rewrite the failed world verdict.

## 1. Input Contract

Accepted inputs:

- an explicit
  `agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0`;
- a wrapper with a `preflight` field containing that same schema.

Rejected inputs:

- raw fixtures;
- consumption reports;
- next-revision plans;
- semantic patch drafts;
- any implicit draft or preflight source.

This strict contract keeps the authority split visible. The apply-request
boundary cannot silently skip the explicit argument-context preflight.

## 2. Output Shape

The pure helper emits:

```text
agent_bridge.lswr.interaction_feedback_patch_apply_request.v0
```

Blocked without a ready preflight:

```json
{
  "apply_request_verdict": "blocked",
  "reason": "source_preflight_not_ready",
  "apply_request": {
    "ready_for_external_submission": false,
    "apply_performed": false,
    "submitted_by_this_tool": false
  }
}
```

Ready with a ready preflight:

```json
{
  "apply_request_verdict": "ready_for_external_executor",
  "reason": "external_apply_request_ready",
  "apply_request": {
    "request_id": "apply_request_arrival_bath_move_002",
    "target_runtime": {
      "runtime_family": "lswr",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "executor": "separate_lswr_patch_executor"
    },
    "patch": {
      "patch_id": "patch_arrival_bath_move_002",
      "op": "semantic_revision",
      "operation_hint": "increase_walkway_clearance_by_repositioning_entity",
      "target_entities": ["bath"],
      "args": {"cell": [5, 2]},
      "required_citations": [
        "verify_patch_arrival_bath_move_001",
        "fb_arrival_crowded_001"
      ]
    },
    "ready_for_external_submission": true,
    "requires_operator_gate": true,
    "requires_external_executor": true,
    "apply_performed": false,
    "submitted_by_this_tool": false
  }
}
```

## 3. Gates

### A1: Ready preflight required

The boundary accepts only a patch execution preflight whose
`preflight_verdict=ready_for_execution_request` and whose resolved patch is
ready.

### A2: No implicit normalization

The boundary blocks raw drafts or fixtures with
`patch_execution_preflight_required`. It must not build a preflight behind the
caller's back.

### A3: External executor only

The boundary may mark the request ready for a separate executor, but must keep
`submitted_by_this_tool=false` and `apply_performed=false`.

### A4: No authority laundering

The boundary blocks a source preflight that claims execution already happened,
grants apply authority to this tool, or weakens read-only guardrails.

### A5: Preserve verification posture

The boundary preserves `source_world_verdict=not_verified`, required citations,
and post-apply verification requirements. It does not rewrite a failed feedback
loop into a verified one.

## 4. Implementation Status

Status: `SOURCE_IMPLEMENTED_VERIFIED_PENDING_ACCEPTANCE`.

Implemented surfaces:

- `agent_bridge.lswr.interaction_feedback_patch_apply_request.v0`
- `build_interaction_feedback_patch_apply_request(...)`
- `render_interaction_feedback_patch_apply_request(...)`
- `crates/bridge/examples/lswr_interaction_feedback_patch_apply_request_smoke.rs`

Current verification evidence:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_patch_apply_request -- --nocapture
```

Passed: 4 tests.

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- --format json --assert-blocked-without-ready-preflight --assert-read-only
```

Passed.

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- --with-fixture-context --format json --assert-ready-with-context --assert-read-only
```

Passed.

```text
bash scripts/verify-biocortex-retrieval-shadow.sh
```

Passed after wiring the blocked-without-ready-preflight and
ready-with-explicit-context apply-request smoke paths into the full verifier.

## 5. Non-Goals

Still not accepted:

- MCP registration;
- default-profile or Codex-essential exposure;
- live runtime lookup by this surface;
- submitting an apply request;
- patch application;
- post-apply outcome ingestion;
- store access;
- memory writes;
- #94 ingestion;
- Onsen mutation;
- verification verdict rewrite.

## 6. Next Slice

The next safe slice is acceptance review for this boundary. Actual patch
application remains a separate authority level and needs an independent runtime
executor design.
