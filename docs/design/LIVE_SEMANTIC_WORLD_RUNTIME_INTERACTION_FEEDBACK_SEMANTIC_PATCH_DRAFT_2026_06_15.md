# Live Semantic World Runtime - Interaction Feedback Semantic Patch Draft

**2026-06-15 - role: read-only dogfood draft / pure AI-readable patch target**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback next revision plan](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_2026_06_15.md)
- [Interaction feedback next revision plan acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_ACCEPTANCE_2026_06_15.md)

Forum anchors:
- `#102` post `#3101`: next-revision plan accepted as
  `ACCEPTED_MODULE_TEST_ONLY`.
- `#102` post `#3103`: semantic patch draft implementation claim.

## 0. Purpose

This slice uses the accepted next-revision plan as an internal AI-readable input
for drafting the next semantic patch target:

```text
fixture / packet / report
  -> next-revision plan
  -> semantic patch draft
```

The draft is intentionally not executable. It gives the agent a constrained
patch target, required citations, and expected-effect requirements, while
leaving concrete world arguments unresolved until a later world-state-aware
step.

## 1. Boundary

Allowed:

- consume an explicit next-revision plan or any input accepted by the plan
  builder;
- preserve the source world verdict;
- carry the next patch ID and target entities from the plan;
- require citation of failed verification and feedback IDs;
- derive semantic intent from failed clauses and feedback issue;
- mark concrete live-world arguments unresolved;
- render a human-auditable Markdown summary;
- run as a pure module/test/example surface.

Not allowed:

- choose concrete world coordinates from stale or missing live state;
- apply a patch;
- mutate Onsen or any live world;
- query a live LSWR host implicitly;
- write memory or store rows;
- call #94 ingestion;
- register a new MCP tool;
- expose anything in the default or Codex-essential profile;
- upgrade `not_verified` because a human rejected or accepted the presentation.

## 2. Output Shape

The pure helper emits:

```text
agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0
```

Required fields:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0",
  "source_plan_verdict": "ready_for_revision",
  "source_world_verdict": "not_verified",
  "draft_verdict": "drafted",
  "semantic_patch_draft": {
    "patch_id": "patch_arrival_bath_move_002",
    "op": "semantic_revision",
    "operation_hint": "increase_walkway_clearance_by_repositioning_entity",
    "target_entities": ["bath"],
    "revision_sources": [
      "verify_patch_arrival_bath_move_001",
      "fb_arrival_crowded_001"
    ],
    "constraints": {
      "failed_clause_ids": ["effect_walkway_clearance_001"],
      "feedback_issue": "visual_density_too_high",
      "preserve_world_verdict": "not_verified"
    },
    "unresolved_arguments": ["patch.args.cell"],
    "requires_live_world_state_for_arguments": true,
    "live_world_state_queried": false,
    "apply_allowed": false,
    "ingest_allowed": false
  }
}
```

## 3. Acceptance Gates

### D1: Accepted plan required

The draft is available only when the source plan is
`plan_verdict=ready_for_revision`. A blocked or laundered plan must yield
`draft_verdict=blocked`.

### D2: Verdict preserved

The draft must keep `source_world_verdict=not_verified` and must not allow human
feedback to rewrite it.

### D3: Required citations retained

The draft must carry both required citations from the plan:

- `verify_patch_arrival_bath_move_001`;
- `fb_arrival_crowded_001`.

### D4: Arguments unresolved honestly

The draft must not invent concrete coordinates. It must set
`unresolved_arguments=["patch.args.cell"]`,
`requires_live_world_state_for_arguments=true`, and
`live_world_state_queried=false`.

### D5: No action side effects

The draft must set `apply_allowed=false`, `ingest_allowed=false`,
`writes_state=false`, `store_access_required=false`, and
`mcp_tool_registered=false`.

## 4. Implementation Status

Status: `SOURCE_IMPLEMENTED_PENDING_ACCEPTANCE`.

Implemented surfaces:

- `build_interaction_feedback_semantic_patch_draft(...)`
- `render_interaction_feedback_semantic_patch_draft(...)`
- `crates/bridge/examples/lswr_interaction_feedback_semantic_patch_draft_smoke.rs`

This is deliberately not an MCP wrapper. If a future MCP surface is useful, it
needs a separate all/niche gate review.
