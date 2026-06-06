# Live Semantic World Runtime - Human Input Mapping

**2026-06-06 - role: P3 human input semantics**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)

Forum anchors:
- `#105` post `#2550`: P3 start notice.

## 0. Purpose

This document maps human mouse, keyboard, selection, decision, and note inputs
to LSWR event and feedback records.

It is docs-only. It does not define a UI, implement capture code, restart Step
D, or add Agent-Bridge tools.

The goal is to make human interaction readable to AI agents without reducing the
human to screenshots or unanchored chat.

## 1. Input Classes

The first human surface should map these input classes:

| Input class | Primary event | Secondary record |
|---|---|---|
| pointer click | `human.click` | optional `human.select` |
| pointer hover/dwell | `human.hover_or_dwell` | optional inferred feedback |
| keyboard movement | `human.move_path` | optional navigation feedback |
| object selection | `human.select` | none |
| accept/reject | `human.accept` / `human.reject` | `feedback.choice` |
| text note | `human.note` | `feedback.explicit_text` |
| undo/revert request | `human.reject` or `runtime.rollback_applied` | feedback/correction |

## 2. Mapping Principles

### MAP-001: Input is first recorded as behavior

The runtime MUST record what the human did before interpreting why they did it.

Example:

```text
mouse click on bath -> human.click
entity becomes selected -> human.select
AI later infers interest -> feedback.inferred_behavior
```

### MAP-002: Anchor whenever possible

Every input event SHOULD include:

- entity IDs if hit-testing resolves a target;
- space/zone ID if the input is spatial but not entity-specific;
- viewport/camera ID;
- screen position for pointer input;
- cause event or patch when input responds to a presented change.

### MAP-003: Decision events do not rewrite verification

`human.accept` and `human.reject` decide whether the human accepts the presented
result or direction. They MUST NOT change any lower-layer
`runtime.verification_result`.

### MAP-004: Inference is separate from raw input

If the system infers preference from dwell, repeated clicks, pathing, or
rejection, that inference MUST be recorded as feedback with confidence. The raw
events remain the ground truth.

## 3. Pointer Events

### 3.1 Click

`human.click` captures the physical click.

Payload:

```json
{
  "input": "mouse",
  "button": "left",
  "screen_position": [840, 512],
  "world_position": [4, 3],
  "hit": {
    "hit_kind": "entity",
    "entity_id": "bath",
    "space_id": "arrival_area",
    "confidence": 0.98
  }
}
```

Rules:

- If hit-testing fails, `hit_kind` may be `space`, `empty`, or `unknown`.
- A click does not imply acceptance.
- A click may cause `human.select` if the client changes selection state.

### 3.2 Hover Or Dwell

`human.hover_or_dwell` captures attention-like behavior.

Payload:

```json
{
  "input": "mouse",
  "screen_position": [812, 498],
  "target": {
    "entity_id": "welcome_sign",
    "space_id": "arrival_area"
  },
  "duration_ms": 1800,
  "threshold_ms": 1000
}
```

Rules:

- Dwell is weak evidence. It should not become preference without normalization.
- Repeated dwell may produce `feedback.inferred_behavior` with confidence.

## 4. Movement Events

`human.move_path` captures navigation, camera motion, or avatar movement.

Payload:

```json
{
  "input": "keyboard",
  "path": [
    {"tick": 120, "position": [2, 3]},
    {"tick": 124, "position": [3, 3]},
    {"tick": 128, "position": [4, 3]}
  ],
  "viewport": "onsen_live_root_viewport",
  "stopped_at": [4, 3],
  "path_quality": {
    "stuck": false,
    "backtracked": false,
    "collisions": 0
  }
}
```

Rules:

- Movement should be compacted into path segments, not one event per key press.
- Stuck, backtrack, repeated pathing, or collision signals may become feedback.
- Movement events should reference the active viewport/camera.

## 5. Selection Events

`human.select` represents a semantic focus change.

Payload:

```json
{
  "selection_state": "selected",
  "selected_entities": ["bath"],
  "previous_entities": [],
  "selection_source": "pointer_click",
  "screen_position": [840, 512]
}
```

Rules:

- Selection is stronger than hover but weaker than accept/reject.
- Selection can be used as context for later notes.
- Multi-select should preserve ordering only if the client exposes ordering.

## 6. Decision Events

Decision events are explicit human review signals.

### 6.1 Accept

`human.accept` payload:

```json
{
  "decision": "accept",
  "decision_scope": "presentation",
  "target_patch_id": "patch_arrival_01",
  "target_event_id": "evt_verify_patch_01",
  "does_not_change_verification": true
}
```

Meaning:

- The human accepts the presented result, direction, or branch.
- This is a verified human decision if the review control is proven to work.
- It does not prove that the world claim was true.

### 6.2 Reject

`human.reject` payload:

```json
{
  "decision": "reject",
  "decision_scope": "presentation",
  "target_patch_id": "patch_arrival_01",
  "target_event_id": "evt_verify_patch_01",
  "reason_hint": "layout_feels_crowded",
  "does_not_change_verification": true
}
```

Meaning:

- The human rejects the result, direction, or branch.
- The runtime may propose rollback or branch comparison after rejection.
- Rejection does not change lower-layer verification.

## 7. Text Notes

`human.note` captures explicit text.

Payload:

```json
{
  "text": "The entrance feels too crowded.",
  "text_language": "en",
  "context": {
    "selected_entities": ["entrance_gate", "welcome_sign"],
    "active_space": "arrival_area",
    "target_patch_id": "patch_arrival_01"
  }
}
```

The companion `feedback.explicit_text` record may normalize it:

```json
{
  "issue": "visual_density_too_high",
  "desired_direction": "more_breathing_room",
  "semantic_axes": ["readability", "arrival_identity"],
  "confidence": 0.72
}
```

Rules:

- Preserve raw text.
- Normalization is advisory.
- If the note references no entity, attach it to active space or session.

## 8. Undo And Rollback Requests

A human may request undo through UI or text.

Represent this as:

1. `human.reject` or `feedback.correction` pointing to the patch/result; then
2. `runtime.rollback_applied` if rollback is executed.

Rollback event payload:

```json
{
  "rollback_group": "arrival_readability_pass_01",
  "target_patch_ids": ["patch_arrival_01"],
  "result": "applied",
  "before_branch": "main",
  "after_branch": "main"
}
```

Rules:

- A request is separate from execution.
- Rollback execution must be verified or reported as not verified/blocked.

## 9. Inferred Feedback

The runtime may infer feedback from behavior.

Examples:

| Pattern | Possible inference | Confidence posture |
|---|---|---|
| repeated click on same non-interactive object | affordance unclear | low |
| long dwell on entity after AI patch | possible attention or concern | low |
| backtracking path after layout change | navigation friction | medium |
| immediate reject after verified patch | disliked result | high for rejection, low for reason |
| accept plus positive note | preferred direction | high |

Inferred feedback record:

```json
{
  "schema": "agent_bridge.lswr.feedback.v0",
  "feedback_id": "fb_inferred_01",
  "source_event_id": "evt_path_01",
  "raw": {
    "kind": "behavior_pattern",
    "pattern": "backtrack_after_patch"
  },
  "normalized": {
    "issue": "navigation_friction",
    "desired_direction": "clearer_path",
    "semantic_axes": ["navigation", "readability"],
    "confidence": 0.55
  },
  "verification_relation": {
    "changes_world_verdict": false,
    "related_verification_event_id": "evt_verify_patch_01"
  }
}
```

## 10. Acceptance Falsifiers

### HI1: Click without hit target

A click on empty space can be represented without fabricating an entity ID.

### HI2: Hover does not become acceptance

A long hover can generate `human.hover_or_dwell` and optional inferred feedback,
but not `human.accept`.

### HI3: Reject does not rewrite verified evidence

Given a verified runtime result and a human reject decision, the verified event
stays verified and the rejection is recorded as separate preference/decision.

### HI4: Raw note survives normalization

Given explicit text feedback, the raw text remains available even if normalized
semantic axes are added.

### HI5: Rollback request and rollback execution are separate

A human undo request can exist even when rollback execution is blocked or not
verified.

### HI6: Movement can express friction

A movement path with backtracking or collisions can produce inferred navigation
feedback without requiring screenshots.

## 11. Non-Goals

P3 does not:

- specify UI layout;
- implement input capture;
- choose Godot signal names;
- store events;
- implement branch/rollback;
- create present review cards;
- ingest memory;
- restart Step D.

## 12. Recommended Next Work

Proceed to P4:

```text
docs/design/LIVE_SEMANTIC_WORLD_RUNTIME_NEXUS_SEED_PRESSURE_2026_06_06.md
```

P4 should test whether the requirements and event schema survive a non-spatial,
causal world seed.
