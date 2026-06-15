# Live Semantic World Runtime - Interaction Feedback Protocol

**2026-06-15 - role: mainline protocol plan / docs-only**

Parent documents:
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Human input mapping](LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md)
- [Step E4d writer preflight](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4D_WRITER_PREFLIGHT_2026_06_15.md)

Forum anchors:
- `#102` post `#3010`: E4d read-only preflight closeout.
- `#102` post `#3014`: start notice for this protocol slice.

## 0. Purpose

This document defines the next mainline LSWR interaction protocol after the
E4d read-only safety rail.

The goal is to make the human-visible surface and the AI-readable surface one
feedback loop:

```text
human interacts with a live world
  -> runtime records semantic input events
  -> AI reads world state, events, feedback, and verification
  -> AI proposes or applies semantic patches
  -> runtime renders and verifies the human-visible result
  -> human keeps interacting, accepts, rejects, or annotates
```

This is not a writer, ingestion, or memory-persistence design. E4d remains a
guardrail around future persistence. This document returns to the product core:
improving the interaction shape between humans, AI agents, and live worlds.

## 1. Design Position

LSWR should not require the AI to constantly screenshot the surface in order to
understand what happened.

The primary readback path should be structured and semantic:

```text
world state
event stream
feedback records
visibility / verification ledger
presentation state
```

Screenshots, OCR, and visual diffing remain useful for audit, regression,
calibration, and contradiction checks. They should not be the ordinary source of
truth when the runtime can emit semantic events directly.

## 2. Interaction State Contract

Every live interaction session should expose one compact state object:

```json
{
  "schema": "agent_bridge.lswr.interaction_state.v0",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 1284,
  "authority_mode": "coedit",
  "participants": [
    {
      "participant_id": "human:owner",
      "participant_kind": "human",
      "surface": "live_viewer",
      "role": "collaborator"
    },
    {
      "participant_id": "ai:codex",
      "participant_kind": "ai",
      "surface": "agent_api",
      "role": "editor"
    }
  ],
  "active_view": {
    "viewport": "onsen_live_root_viewport",
    "camera": "main",
    "selected_entities": ["bath"],
    "active_space": "arrival_area"
  },
  "latest_event_id": "evt_1284",
  "latest_feedback_id": "fb_42",
  "latest_verification_id": "verify_77",
  "presentation_status": {
    "render_fresh": true,
    "visible_change_markers": ["patch_arrival_01"],
    "human_visible_disturbance": {
      "measured": true,
      "flicker_frames": 0
    }
  }
}
```

Rules:

- `interaction_state` is a snapshot, not the source of historical truth.
- It points to events, feedback, and verification records by ID.
- It should be cheap enough for agents to query frequently.
- It must not hide a failed lower-layer verification behind a clean UI state.

## 3. Event Loop Contract

The runtime should emit events at the semantic level instead of forcing agents
to infer interaction from pixels.

Minimum event loop:

```text
human.input
human.focus_changed
ai.patch_proposed
runtime.patch_attempted
runtime.patch_result
runtime.visibility_measured
runtime.verification_result
presentation.state_changed
human.review_decision
feedback.normalized
```

The existing event family names remain valid. The names above describe the
sequence-level contract rather than replacing P2/P3 schemas.

### 3.1 Human Input

Human input is first recorded as behavior:

```json
{
  "event_type": "human.click",
  "refs": {
    "entities": ["bath"],
    "spaces": ["arrival_area"],
    "viewport": "onsen_live_root_viewport",
    "patch_id": null,
    "cause_event_id": null
  },
  "payload": {
    "input": "mouse",
    "screen_position": [840, 512],
    "world_position": [4, 3],
    "hit": {
      "hit_kind": "entity",
      "entity_id": "bath",
      "confidence": 0.98
    }
  }
}
```

The runtime may later normalize behavior into feedback, but raw behavior remains
recoverable.

### 3.2 AI Patch

AI patches must carry expected effects that can be verified:

```json
{
  "event_type": "ai.patch_proposed",
  "payload": {
    "patch": {
      "op": "move",
      "entity": "bath",
      "args": {"cell": [4, 3]},
      "reason": "Improve arrival sightline.",
      "expected_effect": [
        {
          "target": "bath",
          "metric": "screen_area",
          "to_op": ">",
          "to_value": 0.0
        }
      ],
      "rollback_group": "arrival_readability_pass_01"
    }
  }
}
```

The patch may be proposed, applied, blocked, or rolled back, but every state
change must remain queryable.

### 3.3 Presentation State

The human-facing surface should emit a presentation event when a change is
visible, not visible, or visually stale:

```json
{
  "event_type": "presentation.state_changed",
  "refs": {
    "viewport": "onsen_live_root_viewport",
    "patch_id": "patch_arrival_01",
    "cause_event_id": "evt_runtime_patch_result_01"
  },
  "payload": {
    "render_refreshed": true,
    "visible_change": true,
    "change_markers": ["bath"],
    "disturbance": {
      "flicker_frames": 0,
      "camera_jitter": false
    }
  }
}
```

This keeps "logical mutation" separate from "human-visible change".

### 3.4 Human Review

Human review records preference or acceptance of a presentation. It does not
rewrite verification:

```json
{
  "event_type": "human.reject",
  "refs": {
    "patch_id": "patch_arrival_01",
    "cause_event_id": "evt_verify_patch_01"
  },
  "payload": {
    "decision": "reject",
    "decision_scope": "presentation",
    "reason_hint": "layout_feels_crowded",
    "does_not_change_verification": true
  }
}
```

## 4. Agent Readback Contract

The AI should be able to answer these questions without screenshots in the
normal path:

| Question | Primary source |
|---|---|
| What changed? | `runtime.patch_result`, `presentation.state_changed` |
| Did the human see it? | `presentation.state_changed`, `runtime.visibility_measured` |
| Did the expected effect pass? | `runtime.verification_result` |
| What did the human do next? | `human.*` events |
| What did the human mean? | `feedback.*` records with raw source preserved |
| What should be revised? | feedback records plus failed expected-effect clauses |
| What can be rolled back? | patch `rollback_group` and branch state |

The readback API should prefer pages and cursors before subscriptions:

```text
world.interaction_state
world.events.query
world.feedback.query
world.verification.query
world.presentation.query
```

Subscriptions can come later once the query contracts are accepted.

## 5. Human Surface Contract

The first surface remains a live viewer, not a full editor.

Required visible affordances:

- select/focus an entity;
- move or navigate with mouse/keyboard;
- see AI change markers;
- see verification status for AI claims;
- accept or reject a presented change;
- add a short text note anchored to current selection, space, patch, or branch;
- request undo or rollback;
- compare branches once branches exist.

This is enough for humans to shape the world without requiring them to operate a
traditional editor.

## 6. Multi-Agent Contract

Multiple AI agents can share the same event stream only if their authority is
explicit.

Minimum per-agent fields:

```json
{
  "participant_id": "ai:critic:01",
  "participant_kind": "ai",
  "role": "critic",
  "authority_mode": "observe",
  "can_patch": false,
  "can_review": true
}
```

Rules:

- observer/critic agents may write comments or feedback, not world patches;
- editor agents may propose patches in `suggest` mode;
- only authorized agents may apply patches in `coedit` or `autonomous` mode;
- every AI-authored record carries participant identity;
- AI-AI disagreement is represented as feedback or review records, not hidden
  prompt state.

## 7. Safety Boundaries

This protocol does not open persistence or training ingestion.

Hard boundaries:

- no `memory_save` path;
- no #94 ingestion path;
- no `dry_run=false` write tool;
- no default-profile experimental world tools;
- no screenshot-first control loop;
- no hidden verification upgrades;
- no AI patch without reason, expected effect, and rollback group once mutation
  is allowed.

## 8. Acceptance Falsifiers

### IFP1: Human interaction is readable without screenshots

Given a click, selection, note, and reject action, an AI can query the event and
feedback pages and recover the target entity, active space, viewport, raw note,
and decision.

### IFP2: Visible state is not confused with logical state

Given a patch that mutates logical state but produces no rendered change, the
system emits `not_verified` or `presentation.state_changed.visible_change=false`.
It must not report a verified human-visible success.

### IFP3: Human acceptance does not launder failed verification

Given `runtime.verification_result.verdict="not_verified"` and a later
`human.accept`, the verification remains `not_verified`. The accept event only
records human review of the presentation.

### IFP4: Inferred feedback is weaker than explicit feedback

Given a dwell event and an explicit text note, the normalized feedback for the
note has stronger authority than the inferred dwell record unless later
calibration says otherwise.

### IFP5: AI can revise from structured feedback

Given a failed expected-effect clause plus anchored human feedback, an AI can
produce a new patch proposal that cites both sources.

### IFP6: Multi-agent comments do not mutate world state

Given an observer or critic agent, its feedback appears in the event/feedback
stream without changing `world.state` or patch history.

## 9. Minimal Implementation Slice

The next implementation slice should be read-only first:

1. Add a fixture for `interaction_state`, event page, feedback page, and
   presentation page.
2. Add a pure validator that checks event causality and verification honesty.
3. Add a report generator that summarizes:
   - active selection;
   - latest human input;
   - latest AI patch;
   - visible presentation result;
   - latest verification;
   - latest feedback;
   - revision hints.
4. Expose it only as an all-profile/niche dry-run report until accepted.

No writer should be introduced in this slice.

## 10. Recommended Next Work

Proceed with a docs-and-fixtures acceptance slice:

```text
LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_FIXTURE_2026_06_15.md
```

That fixture should contain one complete loop:

```text
human.select -> ai.patch_proposed -> runtime.patch_result
  -> presentation.state_changed -> runtime.verification_result
  -> human.reject -> feedback.explicit_text -> ai.patch_proposed
```

The fixture is accepted only if the AI can recover the next revision direction
from structured state alone, with screenshot evidence optional rather than
required.
