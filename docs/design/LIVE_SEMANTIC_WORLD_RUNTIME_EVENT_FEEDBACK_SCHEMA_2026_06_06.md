# Live Semantic World Runtime - Event And Feedback Schema

**2026-06-06 - role: schema draft / P2**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Phase 0 Step C Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_C_SPEC_2026_06_05.md)

Forum anchors:
- `#105` post `#2548`: P2 start notice.

## 0. Purpose

This document defines the first draft of the LSWR event and feedback bus.

It is docs-only. It does not add MCP tools, modify `crates/bridge`, restart Step
D, or wire #94 ingestion.

The goal is to make human action, AI action, runtime measurement, and human
feedback queryable through one shared semantic world history.

## 1. Design Requirements Covered

This schema covers the following Requirements v1 areas:

- `REQ-ROLE-001`: explicit participant identity;
- `REQ-LOOP-001`: patch result is never an empty ACK;
- `REQ-HUMAN-001`: human feedback is anchored;
- `REQ-HUMAN-002`: human acceptance does not rewrite evidence;
- `REQ-EVENT-001`: event envelope;
- `REQ-EVENT-002`: feedback normalization;
- `REQ-EVENT-003`: replayability;
- `REQ-VERIFY-004`: truth does not improve across layers.

## 2. Event Envelope

Every event should share this envelope:

```json
{
  "schema": "agent_bridge.lswr.event.v0",
  "event_id": "evt_01",
  "event_type": "human.select",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 1284,
  "created_at": "2026-06-06T00:00:00Z",
  "source": {
    "participant_id": "human:owner",
    "participant_kind": "human",
    "authority_mode": "coedit",
    "surface": "onsen_live_view"
  },
  "refs": {
    "entities": ["bath"],
    "spaces": ["arrival_area"],
    "viewport": "onsen_live_root_viewport",
    "patch_id": null,
    "cause_event_id": null
  },
  "payload": {},
  "verification": null,
  "provenance": {
    "adapter": "onsen",
    "source_schema": null,
    "raw_available": true
  }
}
```

### Field Requirements

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | Event schema version |
| `event_id` | yes | Stable event identity |
| `event_type` | yes | Namespaced type |
| `world_id` | yes | World/session root |
| `branch_id` | recommended | Branch or timeline |
| `tick` | recommended | Runtime tick or monotonic sequence |
| `created_at` | yes | Wall-clock timestamp |
| `source` | yes | Participant or runtime source |
| `refs` | yes | World references |
| `payload` | yes | Type-specific data |
| `verification` | optional | Verification object when the event claims evidence |
| `provenance` | yes | Adapter/source/debug detail |

## 3. Event Type Families

### 3.1 Human Input Events

```text
human.move_path
human.click
human.hover_or_dwell
human.select
human.accept
human.reject
human.note
```

Human events represent what the human did, not what the AI inferred.

### 3.2 AI Action Events

```text
ai.patch_proposed
ai.patch_applied
ai.explanation_presented
ai.branch_requested
ai.rollback_requested
```

AI events must carry reason and expected effect for mutating actions.

### 3.3 Runtime Events

```text
runtime.patch_attempted
runtime.patch_result
runtime.visibility_measured
runtime.verification_result
runtime.branch_created
runtime.rollback_applied
runtime.adapter_blocked
runtime.error
```

Runtime events are the trust layer. They should be emitted by the adapter or
runtime, not by an agent summarizing itself.

### 3.4 Feedback Events

```text
feedback.explicit_text
feedback.choice
feedback.preference
feedback.inferred_behavior
feedback.correction
```

Feedback events point to a separate feedback record when normalization is
available.

## 4. Feedback Record

Feedback is an interpretation record, not a replacement for raw events.

```json
{
  "schema": "agent_bridge.lswr.feedback.v0",
  "feedback_id": "fb_01",
  "source_event_id": "evt_note_01",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "created_at": "2026-06-06T00:00:01Z",
  "participant": {
    "participant_id": "human:owner",
    "participant_kind": "human"
  },
  "target": {
    "entities": ["entrance_gate", "welcome_sign"],
    "spaces": ["arrival_area"],
    "patch_id": "patch_arrival_01",
    "viewport": "onsen_live_root_viewport"
  },
  "raw": {
    "kind": "text",
    "text": "The entrance feels too crowded."
  },
  "normalized": {
    "issue": "visual_density_too_high",
    "desired_direction": "more_breathing_room",
    "semantic_axes": ["readability", "arrival_identity"],
    "confidence": 0.72
  },
  "verification_relation": {
    "changes_world_verdict": false,
    "related_verification_event_id": "evt_verify_01"
  }
}
```

### Feedback Rules

- Raw feedback MUST remain recoverable.
- Normalized feedback MUST carry confidence.
- Human acceptance/rejection MUST NOT rewrite lower-layer verification.
- Inferred feedback MUST be marked as inferred and lower confidence than
  explicit feedback unless a later calibration proves otherwise.

## 5. Verification Object

Verification embedded in an event should use the same verdict family as the
requirements:

```json
{
  "verdict": "not_verified",
  "reason": "pixel_coverage_zero",
  "method": "live_viewport_pixel_coverage",
  "verified_to": null,
  "evidence": {
    "screen_area": 0.0,
    "bounds_screen_area": 0.0186224985122681,
    "host_reason": "pixel_coverage_zero",
    "source": "onsen_live_root_viewport"
  }
}
```

Allowed verdicts:

```text
verified
not_verified
blocked
```

Rules:

- `verified_to` is non-null only when `verdict="verified"`.
- `not_verified` and `blocked` must carry stable reasons.
- A human accept/reject event may reference this verification but may not change
  it.

## 6. Example Event Sequences

### 6.1 Human Selects An Entity

```json
{
  "schema": "agent_bridge.lswr.event.v0",
  "event_id": "evt_select_bath_01",
  "event_type": "human.select",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 120,
  "created_at": "2026-06-06T00:00:00Z",
  "source": {
    "participant_id": "human:owner",
    "participant_kind": "human",
    "authority_mode": "coedit",
    "surface": "onsen_live_view"
  },
  "refs": {
    "entities": ["bath"],
    "spaces": [],
    "viewport": "onsen_live_root_viewport",
    "patch_id": null,
    "cause_event_id": null
  },
  "payload": {
    "input": "mouse",
    "screen_position": [840, 512],
    "selection_state": "selected"
  },
  "verification": null,
  "provenance": {
    "adapter": "onsen",
    "source_schema": null,
    "raw_available": true
  }
}
```

### 6.2 AI Proposes A Patch

```json
{
  "schema": "agent_bridge.lswr.event.v0",
  "event_id": "evt_ai_patch_proposed_01",
  "event_type": "ai.patch_proposed",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 121,
  "created_at": "2026-06-06T00:00:02Z",
  "source": {
    "participant_id": "ai:codex",
    "participant_kind": "ai",
    "authority_mode": "suggest",
    "surface": "agent_api"
  },
  "refs": {
    "entities": ["bath"],
    "spaces": ["arrival_area"],
    "viewport": "onsen_live_root_viewport",
    "patch_id": "patch_arrival_01",
    "cause_event_id": "evt_select_bath_01"
  },
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
  },
  "verification": null,
  "provenance": {
    "adapter": "onsen",
    "source_schema": null,
    "raw_available": true
  }
}
```

### 6.3 Runtime Applies And Verifies

```json
{
  "schema": "agent_bridge.lswr.event.v0",
  "event_id": "evt_verify_patch_01",
  "event_type": "runtime.verification_result",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 125,
  "created_at": "2026-06-06T00:00:06Z",
  "source": {
    "participant_id": "runtime:onsen_adapter",
    "participant_kind": "runtime",
    "authority_mode": "coedit",
    "surface": "world_adapter"
  },
  "refs": {
    "entities": ["bath"],
    "spaces": ["arrival_area"],
    "viewport": "onsen_live_root_viewport",
    "patch_id": "patch_arrival_01",
    "cause_event_id": "evt_ai_patch_proposed_01"
  },
  "payload": {
    "applied": true,
    "before": {"cell": [2, 3]},
    "after": {"cell": [4, 3]},
    "render_refreshed": true
  },
  "verification": {
    "verdict": "verified",
    "reason": null,
    "method": "live_viewport_pixel_coverage",
    "verified_to": "onsen_live_root_viewport",
    "evidence": {
      "screen_area": 0.005815625,
      "bounds_screen_area": 0.0186224985122681,
      "host_reason": null,
      "source": "onsen_live_root_viewport"
    }
  },
  "provenance": {
    "adapter": "onsen",
    "source_schema": "agent_bridge.world_tool.v0",
    "raw_available": false
  }
}
```

### 6.4 Human Rejects The Presentation

```json
{
  "schema": "agent_bridge.lswr.event.v0",
  "event_id": "evt_human_reject_01",
  "event_type": "human.reject",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "tick": 130,
  "created_at": "2026-06-06T00:00:12Z",
  "source": {
    "participant_id": "human:owner",
    "participant_kind": "human",
    "authority_mode": "coedit",
    "surface": "review_card"
  },
  "refs": {
    "entities": ["bath"],
    "spaces": ["arrival_area"],
    "viewport": "onsen_live_root_viewport",
    "patch_id": "patch_arrival_01",
    "cause_event_id": "evt_verify_patch_01"
  },
  "payload": {
    "decision": "reject",
    "decision_scope": "presentation",
    "does_not_change_verification": true
  },
  "verification": null,
  "provenance": {
    "adapter": "agent_bridge_present",
    "source_schema": "present_approval/v0",
    "raw_available": true
  }
}
```

The rejection does not change `evt_verify_patch_01.verification.verdict`. It is
new human feedback about whether the verified change was desirable.

## 7. Query Contracts

Future agent APIs should support read-only event and feedback queries before
adding subscriptions.

### `world.events.query`

Input:

```json
{
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "cursor": null,
  "event_types": ["human.select", "runtime.verification_result"],
  "entity_ids": ["bath"],
  "limit": 50
}
```

Output:

```json
{
  "schema": "agent_bridge.lswr.events_page.v0",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "cursor_next": "evt_130",
  "events": []
}
```

### `world.feedback.query`

Input:

```json
{
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "target": {
    "entities": ["bath"],
    "spaces": ["arrival_area"]
  },
  "limit": 50
}
```

Output:

```json
{
  "schema": "agent_bridge.lswr.feedback_page.v0",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "cursor_next": "fb_50",
  "feedback": []
}
```

## 8. Acceptance Falsifiers

P2 is accepted only if these cases are representable without changing the
schema:

### EF1: Human reject does not rewrite verification

Given a `runtime.verification_result` with `verdict="verified"` and a later
`human.reject`, the verification event remains `verified`; the rejection is a
separate human decision event.

### EF2: Inert render failure is representable

Given an AI patch that applies logically but the render is inert, the runtime can
emit `runtime.verification_result` with `verdict="not_verified"` and reason such
as `pixel_coverage_zero` or `render_not_changed`.

### EF3: Adapter safety block is representable

Given a non-loopback host or unsafe operation, the runtime can emit
`runtime.adapter_blocked` or `runtime.verification_result` with
`verdict="blocked"` and stable reason.

### EF4: Raw and normalized feedback coexist

Given human text feedback, the raw text and normalized semantic interpretation
can coexist, and normalized confidence is explicit.

### EF5: Event causality is recoverable

Given a selected entity, AI patch proposal, runtime result, and human decision,
the event chain can be followed through `cause_event_id` and `patch_id`.

### EF6: Nexus-style non-visual evidence is possible

Given a future causal/governance world, the event envelope can carry causal
verification evidence without requiring Onsen-specific `screen_area` fields in
the core envelope.

## 9. Non-Goals

P2 does not:

- implement storage;
- add MCP tools;
- define a subscription transport;
- choose a database;
- ingest memory;
- define branch merge semantics;
- restart Step D;
- decide Nexus adapter details.

## 10. Recommended Next Work

Proceed to P3:

```text
docs/design/LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md
```

P3 should map concrete mouse/keyboard/select/accept/reject behaviors to the
event types defined here.
