# Live Semantic World Runtime - Interaction Feedback Next Revision Plan

**2026-06-15 - role: read-only dogfood plan / pure AI-readable revision target**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback evidence packet consumption](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_EVIDENCE_PACKET_CONSUMPTION_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report MCP gate](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_GATE_2026_06_15.md)
- [Interaction feedback next revision plan acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback semantic patch draft acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_ACCEPTANCE_2026_06_15.md)

Forum anchors:
- `#102` post `#3095`: MCP surface smoke runner landed at `ee16c33`.
- `#102` post `#3099`: next-revision plan implementation landed at `eee98a3`
  and merged with concurrent GitHub work at `5ddcca5`.

## 0. Purpose

This slice dogfoods the accepted interaction-feedback consumption report by
turning it into an explicit next-revision planning object:

```text
fixture / packet / preflight / consumption report
  -> accepted consumption report
  -> next-revision plan
```

The plan is meant for AI agents. It answers: given the same feedback and failed
verification that a human can audit, what should the next AI revision cite and
what patch target should it plan around?

It intentionally does not execute that patch.

## 1. Boundary

Allowed:

- consume an explicit fixture, evidence packet, preflight object, or consumption
  report;
- preserve the source world verdict;
- select the next revision patch ID already present in readback;
- expose the failed verification IDs and human feedback IDs that must be cited;
- render a human-auditable Markdown summary;
- run as a pure module/test/example surface.

Not allowed:

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
agent_bridge.lswr.interaction_feedback_next_revision_plan.v0
```

Required fields:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_next_revision_plan.v0",
  "source_schema": "agent_bridge.lswr.interaction_feedback_consumption_report.v0",
  "source_accepted": true,
  "source_world_verdict": "not_verified",
  "plan_verdict": "ready_for_revision",
  "next_revision": {
    "patch_id": "patch_arrival_bath_move_002",
    "failed_clause_ids": ["effect_walkway_clearance_001"],
    "feedback_issue": "visual_density_too_high",
    "must_cite": [
      "verify_patch_arrival_bath_move_001",
      "fb_arrival_crowded_001"
    ],
    "preserved_world_verdict": "not_verified",
    "allowed_to_apply": false,
    "allowed_to_ingest": false
  }
}
```

## 3. Acceptance Gates

### R1: Source report accepted

The plan is ready only if the consumption report is accepted. Missing input,
failed guardrails, or a blocked preflight must produce `plan_verdict=blocked`.

### R2: Verdict preserved

The plan must preserve `source_world_verdict` and
`next_revision.preserved_world_verdict`. If the source tries to launder a failed
claim into `verified`, the plan is blocked and the suspicious source verdict
remains visible.

### R3: Revision sources present

The plan must expose both the failed verification source and feedback source in
`next_revision.must_cite`.

### R4: No action side effects

The plan must set `allowed_to_apply=false`, `allowed_to_ingest=false`,
`writes_state=false`, `store_access_required=false`, and
`implicit_live_runtime_lookup_attempted=false`.

### R5: Human-auditable Markdown

The Markdown renderer must show the plan verdict, source verdict, failed
clauses, feedback issue, required citations, and the no-action contract.

## 4. Implementation Status

Status: `ACCEPTED_MODULE_TEST_ONLY`.

Implemented surfaces:

- `build_interaction_feedback_next_revision_plan(...)`
- `render_interaction_feedback_next_revision_plan(...)`
- `crates/bridge/examples/lswr_interaction_feedback_next_revision_plan_smoke.rs`

This is deliberately not an MCP wrapper. If a future MCP surface is useful, it
needs the same separate all/niche gate review used for the consumption report.

The downstream semantic patch draft follow-up is now accepted as module/test-only
in
`LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_ACCEPTANCE_2026_06_15.md`.
