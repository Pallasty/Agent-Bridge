# Live Semantic World Runtime - Tiny Web Prototype Spec

**2026-06-06 - role: P7 runnable prototype contract**

Parent documents:
- [Core extraction criteria](LIVE_SEMANTIC_WORLD_RUNTIME_CORE_EXTRACTION_CRITERIA_2026_06_06.md)
- [Engine/API research refresh](LIVE_SEMANTIC_WORLD_RUNTIME_ENGINE_API_REFRESH_2026_06_06.md)

Forum anchors:
- `#105` post `#2558`: P7 start notice.

## 0. Status

This document is docs-only. It does not implement the prototype, modify
`crates/bridge`, resume Step D, register MCP tools, or open #92/#94 wiring.

It defines a smallest useful web-first LSWR prototype contract.

## 1. Prototype Goal

Build one browser scene where:

```text
agent applies semantic action
  -> semantic world JSON changes
  -> Three.js projection changes
  -> human can click/drag/accept/reject
  -> runtime records structured events and verification
  -> agent reads JSON state/evidence, not screenshots
```

This is not a game engine selection. It is a contract test for LSWR's
interaction loop.

## 2. Non-Goals

The prototype must not:

- use editor GUI automation as the design path;
- depend on screenshots as the primary agent perception path;
- implement durable memory or learning;
- ingest #94 verified outcomes;
- register Agent-Bridge MCP tools;
- implement multiplayer;
- implement physics beyond simple hit-test and bounds checks;
- claim to be `world-core`.

## 3. Minimum Scene Shape

Schema:

```text
agent_bridge.lswr.web_scene.v0
```

Example:

```json
{
  "schema": "agent_bridge.lswr.web_scene.v0",
  "world": {
    "world_id": "lswr_web_proto_01",
    "branch_id": "main",
    "tick": 0,
    "bounds": {"x": [-6, 6], "y": [0, 4], "z": [-6, 6]},
    "authority_mode": "coedit"
  },
  "entities": [
    {
      "entity_id": "platform",
      "kind": "surface",
      "label": "Platform",
      "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [8, 0.2, 8]},
      "geometry": {"type": "box"},
      "material": {"color": "#6f7d8c", "opacity": 1.0},
      "state": {"selectable": false, "locked": true},
      "tags": ["ground"]
    },
    {
      "entity_id": "cube_01",
      "kind": "object",
      "label": "Cube 01",
      "transform": {"position": [0, 1, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
      "geometry": {"type": "box"},
      "material": {"color": "#2f80ed", "opacity": 1.0},
      "state": {"selectable": true, "selected": false, "verification": "verified"},
      "tags": ["demo", "movable"]
    }
  ],
  "events": [],
  "verification": [],
  "rollback": {
    "next_group_id": "rb_001",
    "available_groups": []
  }
}
```

Rules:

- `world_id`, `branch_id`, and `entity_id` are stable IDs.
- The semantic JSON is the source of truth.
- The Three.js scene is a projection, not the source of truth.
- Projection metadata must map each rendered object back to `entity_id`.

## 4. Three Agent Actions

Schema:

```text
agent_bridge.lswr.action.v0
```

### 4.1 Add Entity

```json
{
  "action_id": "act_add_cube_02",
  "action_type": "add_entity",
  "source": {"participant_id": "ai:codex", "authority_mode": "coedit"},
  "rollback_group": "rb_001",
  "payload": {
    "entity": {
      "entity_id": "cube_02",
      "kind": "object",
      "label": "Cube 02",
      "transform": {"position": [2, 1, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
      "geometry": {"type": "box"},
      "material": {"color": "#f2994a", "opacity": 1.0},
      "state": {"selectable": true},
      "tags": ["demo", "movable"]
    }
  },
  "expected_effect": {
    "entity_present": "cube_02",
    "human_visible": true,
    "hit_testable": true
  }
}
```

### 4.2 Move Entity

```json
{
  "action_id": "act_move_cube_01",
  "action_type": "move_entity",
  "source": {"participant_id": "ai:codex", "authority_mode": "coedit"},
  "rollback_group": "rb_002",
  "payload": {
    "entity_id": "cube_01",
    "position": [-2, 1, 0]
  },
  "expected_effect": {
    "entity_present": "cube_01",
    "position": [-2, 1, 0],
    "human_visible": true
  }
}
```

### 4.3 Set Material

```json
{
  "action_id": "act_material_cube_01",
  "action_type": "set_material",
  "source": {"participant_id": "ai:codex", "authority_mode": "coedit"},
  "rollback_group": "rb_003",
  "payload": {
    "entity_id": "cube_01",
    "material": {"color": "#27ae60", "opacity": 1.0}
  },
  "expected_effect": {
    "entity_present": "cube_01",
    "material_color": "#27ae60",
    "human_visible": true
  }
}
```

Action rules:

- Every mutating action stores a before snapshot for its rollback group.
- Every action emits `runtime.action_attempted`.
- Applied actions emit `runtime.action_result`.
- Rejected actions emit `runtime.action_result` with `verification.verdict="blocked"`.
- Applied but unproven actions emit `verification.verdict="not_verified"`.

## 5. Three Human Events

Schema:

```text
agent_bridge.lswr.event.v0
```

### 5.1 Select

```json
{
  "event_type": "human.select",
  "source": {"participant_id": "human:owner", "surface": "web_scene"},
  "refs": {"entities": ["cube_01"], "viewport": "main_canvas"},
  "payload": {"selection_state": "selected", "screen_position": [640, 360]}
}
```

### 5.2 Drag Move

```json
{
  "event_type": "human.drag_move",
  "source": {"participant_id": "human:owner", "surface": "web_scene"},
  "refs": {"entities": ["cube_01"], "viewport": "main_canvas"},
  "payload": {
    "from": [0, 1, 0],
    "to": [1, 1, -1],
    "input": "mouse"
  }
}
```

The drag produces a semantic `move_entity` action with
`source.participant_id="human:owner"`.

### 5.3 Decision

```json
{
  "event_type": "human.reject",
  "source": {"participant_id": "human:owner", "surface": "web_scene"},
  "refs": {"actions": ["act_material_cube_01"], "entities": ["cube_01"]},
  "payload": {
    "decision": "reject",
    "reason_hint": "color_conflicts_with_scene",
    "does_not_change_verification": true
  }
}
```

Decision rules:

- `human.accept` and `human.reject` never rewrite lower-layer verification.
- A reject may request rollback.
- A note can be added later; it is not required for the tiny prototype.

## 6. Three Verification Cases

### 6.1 Verified

An action is `verified` when all required semantic and projection checks pass.

Required checks for `add_entity`:

- entity exists in semantic state;
- projection object exists with matching `entity_id`;
- object has non-zero bounds;
- raycast or object registry can identify it;
- material opacity is greater than zero;
- position is inside world bounds.

Example:

```json
{
  "verdict": "verified",
  "reason": null,
  "method": "web_scene_projection_check",
  "verified_to": "entity:cube_02",
  "evidence": {
    "adapter_kind": "threejs_web",
    "entity_id": "cube_02",
    "projected": true,
    "bounds_nonzero": true,
    "hit_testable": true,
    "inside_bounds": true
  }
}
```

### 6.2 Not Verified

An action is `not_verified` when it was applied semantically but projection or
evidence does not prove the expected effect.

Example reasons:

- `projection_object_absent`;
- `bounds_zero`;
- `material_opacity_zero`;
- `hit_test_failed`;
- `position_mismatch`;
- `expected_effect_absent`.

The human-visible state must show an explicit unconfirmed marker for the target
entity or action. It must not display success wording.

### 6.3 Blocked

An action is `blocked` before mutation when it violates the prototype policy.

Example reasons:

- `duplicate_entity_id`;
- `entity_not_found`;
- `position_out_of_bounds`;
- `locked_entity`;
- `invalid_geometry`;
- `authority_mode_locked`.

Blocked actions must not mutate semantic state.

## 7. Rollback Path

Rollback is action-log based.

For every mutating action:

```json
{
  "rollback_group": "rb_002",
  "before": {"entities": [{"entity_id": "cube_01", "transform": {"position": [0, 1, 0]}}]},
  "after": {"entities": [{"entity_id": "cube_01", "transform": {"position": [-2, 1, 0]}}]},
  "actions": ["act_move_cube_01"],
  "verification_event_id": "evt_verify_move_cube_01"
}
```

Rollback operation:

```json
{
  "action_type": "rollback",
  "payload": {"rollback_group": "rb_002"},
  "expected_effect": {
    "entity_present": "cube_01",
    "position": [0, 1, 0]
  }
}
```

Rules:

- rollback emits `runtime.rollback_applied`;
- rollback receives its own verification;
- rollback failure is `not_verified`, not silent success;
- rollback does not delete the event history.

## 8. Minimal API Contract

The prototype may be a local web app with in-memory state. It should still use
clear API-like functions:

| Function | Purpose |
|---|---|
| `world_get()` | Return current semantic state |
| `world_apply(action)` | Validate, apply, project, and verify one action |
| `world_events_query(filter)` | Return event log |
| `world_evidence_query(refs)` | Return verification/evidence records |
| `world_rollback(group_id)` | Apply rollback path |
| `world_export()` | Return semantic state plus event/evidence log |

These can be JavaScript functions first. HTTP or MCP wrapping is out of scope.

## 9. Human Surface

Minimum visible UI:

- full canvas scene;
- selected entity outline;
- action/evidence panel;
- accept/reject controls for the latest action;
- explicit unconfirmed state for `not_verified`;
- blocked action row with reason.

The UI must not rely on instructional text to make the prototype meaningful. It
should show state changes directly.

## 10. Agent Readback

The agent readback packet must include:

```json
{
  "world": {},
  "entities": [],
  "events": [],
  "verification": [],
  "rollback": {},
  "projection": {
    "adapter": "threejs_web",
    "projected_entities": [],
    "unprojected_entities": []
  }
}
```

The agent may request screenshots for audit, but acceptance depends on this
structured packet.

## 11. Acceptance Gates

| Gate | Requirement |
|---|---|
| `WEB-001` | Agent can add an entity and read back semantic + projection evidence |
| `WEB-002` | Agent can move an entity and see verified position evidence |
| `WEB-003` | Human can select an entity and produce `human.select` |
| `WEB-004` | Human can reject an action without rewriting verification |
| `WEB-005` | A forced projection miss produces `not_verified` and an unconfirmed visual state |
| `WEB-006` | A blocked action leaves semantic state unchanged |
| `WEB-007` | Rollback restores prior semantic state and emits rollback verification |
| `WEB-008` | Agent readback is sufficient without screenshot inspection |

## 12. P8 Recommendation

The next package can implement this as an isolated prototype, not in
`crates/bridge`:

```text
agent-bridge-lswr-web-prototype/
  package.json
  src/
    world.ts
    projection.ts
    verification.ts
    events.ts
    rollback.ts
    app.tsx
```

Keep it disposable until the interaction contract proves useful.
