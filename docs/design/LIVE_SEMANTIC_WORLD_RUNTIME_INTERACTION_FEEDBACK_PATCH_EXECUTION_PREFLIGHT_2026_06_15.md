# Live Semantic World Runtime - Interaction Feedback Patch Execution Preflight

**2026-06-15 - role: read-only execution gate / pure preflight**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback next revision plan](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_2026_06_15.md)
- [Interaction feedback semantic patch draft](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_2026_06_15.md)
- [Interaction feedback semantic patch draft acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback patch execution preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_ACCEPTANCE_2026_06_15.md)

Forum anchors:
- `#102` post `#3109`: execution preflight implementation claim.

## 0. Purpose

This slice adds a pure execution-gate preflight after the accepted semantic
patch draft:

```text
fixture / packet / report
  -> next-revision plan
  -> semantic patch draft
  -> patch execution preflight
```

The preflight answers one narrow question: can the draft now be handed to a
separate patch-apply request without inventing missing world arguments?

It may resolve draft arguments only from explicit argument context supplied by
the caller. It does not query live runtime state, apply the patch, mutate Onsen,
ingest outcomes, write memory/store rows, register MCP tools, or rewrite the
failed world verdict.

## 1. Input Contract

Accepted inputs:

- an explicit `agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0`;
- a wrapper with `draft` plus `argument_context`;
- a fixture/report/plan input that can be normalized into a semantic patch
  draft, still subject to the same explicit argument-context gate.

Argument context schema:

```text
agent_bridge.lswr.interaction_feedback_argument_context.v0
```

The preflight accepts context only when all of these hold:

- `live_runtime_queried_by_preflight=false`;
- `candidate_arguments` contains `argument_path=patch.args.cell`;
- the selected candidate has a concrete `value`;
- the selected candidate declares `satisfies_expected_effect=true`.

Missing or invalid context blocks with `explicit_argument_context_required`,
`argument_context_schema_mismatch`, or
`no_satisfying_patch_args_cell_candidate`.

## 2. Output Shape

The pure helper emits:

```text
agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0
```

Blocked without explicit context:

```json
{
  "preflight_verdict": "blocked",
  "reason": "explicit_argument_context_required",
  "failure_reasons": [
    "explicit_argument_context_required",
    "patch_args_cell_unresolved"
  ],
  "resolved_patch": {
    "ready_for_execution_request": false,
    "execution_performed": false,
    "apply_allowed_by_this_tool": false
  }
}
```

Ready with explicit context:

```json
{
  "preflight_verdict": "ready_for_execution_request",
  "reason": "explicit_argument_context_execution_preflight_ready",
  "resolved_patch": {
    "patch_id": "patch_arrival_bath_move_002",
    "op": "semantic_revision",
    "operation_hint": "increase_walkway_clearance_by_repositioning_entity",
    "target_entities": ["bath"],
    "args": {"cell": [5, 2]},
    "resolved_arguments": {"patch.args.cell": [5, 2]},
    "required_citations": [
      "verify_patch_arrival_bath_move_001",
      "fb_arrival_crowded_001"
    ],
    "ready_for_execution_request": true,
    "execution_performed": false,
    "apply_allowed_by_this_tool": false,
    "ingest_allowed_by_this_tool": false
  }
}
```

## 3. Gates

### E1: Explicit context required

The preflight must not infer concrete patch arguments from the fixture, stale
state, or a hidden live query. Without accepted `argument_context`, it blocks.

### E2: No live lookup by preflight

The preflight must set `implicit_live_runtime_lookup_attempted=false` and must
reject context claiming `live_runtime_queried_by_preflight=true`.

### E3: Explicit candidate can resolve args

When a satisfying explicit candidate is supplied for `patch.args.cell`, the
preflight may copy it into `resolved_patch.args.cell` and
`resolved_patch.resolved_arguments`.

### E4: No execution side effects

The preflight must keep `execution_performed=false`,
`apply_allowed_by_this_tool=false`, `ingest_allowed_by_this_tool=false`,
`writes_state=false`, `store_access_required=false`, and
`mcp_tool_registered=false`.

### E5: No verdict rewrite

The source draft must still carry `source_world_verdict=not_verified`. A
laundered source draft or plan blocks even when explicit argument context is
present.

## 4. Implementation Status

Status: `ACCEPTED_PREFLIGHT_ONLY`.

Implemented surfaces:

- `build_interaction_feedback_patch_execution_preflight(...)`
- `render_interaction_feedback_patch_execution_preflight(...)`
- `crates/bridge/examples/lswr_interaction_feedback_patch_execution_preflight_smoke.rs`

This is deliberately not an MCP wrapper and deliberately not a patch executor.
Any future execution surface needs a separate gate with live runtime, apply, and
outcome-ingestion boundaries reviewed independently.

Acceptance is recorded in
`LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_ACCEPTANCE_2026_06_15.md`.
