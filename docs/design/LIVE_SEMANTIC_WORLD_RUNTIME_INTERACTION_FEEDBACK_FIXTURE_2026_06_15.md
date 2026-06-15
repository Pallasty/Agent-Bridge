# Live Semantic World Runtime - Interaction Feedback Fixture

**2026-06-15 - role: fixture / docs-only**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Human input mapping](LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)

Forum anchors:
- `#102` post `#3015`: interaction feedback protocol done.
- `#102` post `#3016`: E4 deploy/doc boundary follow-up.
- `#102` post `#3018`: start notice for this fixture slice.

## 0. Purpose

This fixture makes the interaction feedback protocol concrete.

It models one complete structured loop:

```text
human.select
  -> ai.patch_proposed
  -> runtime.patch_result
  -> presentation.state_changed
  -> runtime.verification_result
  -> human.reject
  -> feedback.explicit_text
  -> ai.patch_proposed
```

The fixture is intentionally docs-only. It does not add code, register MCP
tools, touch Onsen, open a writer, call `memory_save`, or introduce #94
ingestion.

## 1. Fixture Scenario

Scenario:

- The human selects the `bath` in `arrival_area`.
- The AI proposes moving the bath to improve arrival sightline.
- The runtime applies the logical patch.
- The presentation refreshes and the human-visible surface changes.
- Verification confirms the bath is visible, but one expected-effect clause
  fails because the walkway remains too narrow.
- The human rejects the presentation and adds a text note.
- The AI proposes a revision that cites both the failed expected-effect clause
  and the explicit human feedback.

This proves the key distinction:

```text
logical patch applied != human-visible success != human preference accepted
```

## 2. Machine-Checkable Fixture

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_fixture.v0",
  "fixture_id": "lswr_interaction_feedback_loop_001",
  "world_id": "onsen_live_session",
  "branch_id": "main",
  "requires_screenshot_for_primary_readback": false,
  "world_summary": {
    "spaces": [
      {
        "space_id": "arrival_area",
        "role": "arrival_readability_test"
      }
    ],
    "entities": [
      {
        "entity_id": "bath",
        "semantic_role": "arrival_landmark",
        "cell": [2, 3],
        "screen_area": 0.004,
        "walkway_clearance_cells": 1
      }
    ]
  },
  "interaction_state_before": {
    "schema": "agent_bridge.lswr.interaction_state.v0",
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "tick": 1200,
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
      "selected_entities": [],
      "active_space": "arrival_area"
    },
    "latest_event_id": null,
    "latest_feedback_id": null,
    "latest_verification_id": null,
    "presentation_status": {
      "render_fresh": true,
      "visible_change_markers": [],
      "human_visible_disturbance": {
        "measured": true,
        "flicker_frames": 0
      }
    }
  },
  "events": [
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_human_select_bath_001",
      "event_type": "human.select",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1201,
      "created_at": "2026-06-15T10:00:01Z",
      "source": {
        "participant_id": "human:owner",
        "participant_kind": "human",
        "authority_mode": "coedit",
        "surface": "live_viewer"
      },
      "refs": {
        "entities": ["bath"],
        "spaces": ["arrival_area"],
        "viewport": "onsen_live_root_viewport",
        "patch_id": null,
        "cause_event_id": null
      },
      "payload": {
        "selection_state": "selected",
        "selected_entities": ["bath"],
        "previous_entities": [],
        "selection_source": "pointer_click",
        "screen_position": [840, 512]
      },
      "verification": null,
      "provenance": {
        "adapter": "onsen",
        "source_schema": "live_viewer_input/v0",
        "raw_available": true
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_ai_patch_proposed_001",
      "event_type": "ai.patch_proposed",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1202,
      "created_at": "2026-06-15T10:00:02Z",
      "source": {
        "participant_id": "ai:codex",
        "participant_kind": "ai",
        "authority_mode": "coedit",
        "surface": "agent_api"
      },
      "refs": {
        "entities": ["bath"],
        "spaces": ["arrival_area"],
        "viewport": "onsen_live_root_viewport",
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_human_select_bath_001"
      },
      "payload": {
        "patch": {
          "op": "move",
          "entity": "bath",
          "args": {
            "cell": [4, 3]
          },
          "reason": "Improve arrival sightline while keeping the bath readable from the entry camera.",
          "expected_effect": [
            {
              "clause_id": "effect_bath_visible_001",
              "target": "bath",
              "metric": "screen_area",
              "to_op": ">",
              "to_value": 0.0
            },
            {
              "clause_id": "effect_walkway_clearance_001",
              "target": "arrival_area.main_walkway",
              "metric": "walkway_clearance_cells",
              "to_op": ">=",
              "to_value": 2
            }
          ],
          "rollback_group": "arrival_readability_pass_001"
        }
      },
      "verification": null,
      "provenance": {
        "adapter": "agent_bridge_world_patch",
        "source_schema": "world_patch_request/v0",
        "raw_available": true
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_runtime_patch_result_001",
      "event_type": "runtime.patch_result",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1203,
      "created_at": "2026-06-15T10:00:03Z",
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
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_ai_patch_proposed_001"
      },
      "payload": {
        "attempted": true,
        "applied": true,
        "before": {
          "bath.cell": [2, 3],
          "bath.screen_area": 0.004,
          "arrival_area.main_walkway.walkway_clearance_cells": 1
        },
        "after": {
          "bath.cell": [4, 3],
          "bath.screen_area": 0.006,
          "arrival_area.main_walkway.walkway_clearance_cells": 1
        },
        "affected_entities": ["bath"],
        "rollback_group": "arrival_readability_pass_001"
      },
      "verification": null,
      "provenance": {
        "adapter": "onsen",
        "source_schema": "world_patch_result/v0",
        "raw_available": false
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_presentation_changed_001",
      "event_type": "presentation.state_changed",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1204,
      "created_at": "2026-06-15T10:00:04Z",
      "source": {
        "participant_id": "runtime:onsen_presenter",
        "participant_kind": "runtime",
        "authority_mode": "coedit",
        "surface": "live_viewer"
      },
      "refs": {
        "entities": ["bath"],
        "spaces": ["arrival_area"],
        "viewport": "onsen_live_root_viewport",
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_runtime_patch_result_001"
      },
      "payload": {
        "render_refreshed": true,
        "visible_change": true,
        "change_markers": ["bath"],
        "disturbance": {
          "flicker_frames": 0,
          "camera_jitter": false
        }
      },
      "verification": null,
      "provenance": {
        "adapter": "onsen",
        "source_schema": "presentation_state/v0",
        "raw_available": false
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_verify_patch_001",
      "event_type": "runtime.verification_result",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1205,
      "created_at": "2026-06-15T10:00:05Z",
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
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_presentation_changed_001"
      },
      "payload": {
        "expected_effect_results": [
          {
            "clause_id": "effect_bath_visible_001",
            "target": "bath",
            "metric": "screen_area",
            "observed": 0.006,
            "to_op": ">",
            "to_value": 0.0,
            "passed": true
          },
          {
            "clause_id": "effect_walkway_clearance_001",
            "target": "arrival_area.main_walkway",
            "metric": "walkway_clearance_cells",
            "observed": 1,
            "to_op": ">=",
            "to_value": 2,
            "passed": false
          }
        ]
      },
      "verification": {
        "verification_id": "verify_patch_arrival_bath_move_001",
        "verdict": "not_verified",
        "reason": "expected_effect_clause_failed",
        "method": "expected_effect_falsifier",
        "verified_to": null,
        "evidence": {
          "failed_clause_ids": ["effect_walkway_clearance_001"],
          "host_reason": "walkway_clearance_below_threshold",
          "source": "onsen_live_root_viewport"
        }
      },
      "provenance": {
        "adapter": "onsen",
        "source_schema": "expected_effect_verification/v0",
        "raw_available": false
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_human_reject_001",
      "event_type": "human.reject",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1206,
      "created_at": "2026-06-15T10:00:06Z",
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
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_verify_patch_001"
      },
      "payload": {
        "decision": "reject",
        "decision_scope": "presentation",
        "reason_hint": "layout_feels_crowded",
        "does_not_change_verification": true
      },
      "verification": null,
      "provenance": {
        "adapter": "agent_bridge_present",
        "source_schema": "present_approval/v0",
        "raw_available": true
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_feedback_text_001",
      "event_type": "feedback.explicit_text",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1207,
      "created_at": "2026-06-15T10:00:07Z",
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
        "patch_id": "patch_arrival_bath_move_001",
        "cause_event_id": "evt_human_reject_001"
      },
      "payload": {
        "feedback_id": "fb_arrival_crowded_001",
        "raw": {
          "kind": "text",
          "text": "The bath is visible now, but the entrance still feels crowded."
        }
      },
      "verification": null,
      "provenance": {
        "adapter": "agent_bridge_present",
        "source_schema": "feedback_text/v0",
        "raw_available": true
      }
    },
    {
      "schema": "agent_bridge.lswr.event.v0",
      "event_id": "evt_ai_patch_proposed_002",
      "event_type": "ai.patch_proposed",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "tick": 1208,
      "created_at": "2026-06-15T10:00:08Z",
      "source": {
        "participant_id": "ai:codex",
        "participant_kind": "ai",
        "authority_mode": "coedit",
        "surface": "agent_api"
      },
      "refs": {
        "entities": ["bath"],
        "spaces": ["arrival_area"],
        "viewport": "onsen_live_root_viewport",
        "patch_id": "patch_arrival_bath_move_002",
        "cause_event_id": "evt_feedback_text_001"
      },
      "payload": {
        "patch": {
          "op": "move",
          "entity": "bath",
          "args": {
            "cell": [5, 2]
          },
          "reason": "Revision after failed walkway clearance and explicit crowded-layout feedback.",
          "revision_sources": [
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
          ],
          "expected_effect": [
            {
              "clause_id": "effect_bath_visible_002",
              "target": "bath",
              "metric": "screen_area",
              "to_op": ">",
              "to_value": 0.0
            },
            {
              "clause_id": "effect_walkway_clearance_002",
              "target": "arrival_area.main_walkway",
              "metric": "walkway_clearance_cells",
              "to_op": ">=",
              "to_value": 2
            }
          ],
          "rollback_group": "arrival_readability_pass_002"
        }
      },
      "verification": null,
      "provenance": {
        "adapter": "agent_bridge_world_patch",
        "source_schema": "world_patch_request/v0",
        "raw_available": true
      }
    }
  ],
  "feedback": [
    {
      "schema": "agent_bridge.lswr.feedback.v0",
      "feedback_id": "fb_arrival_crowded_001",
      "source_event_id": "evt_feedback_text_001",
      "world_id": "onsen_live_session",
      "branch_id": "main",
      "created_at": "2026-06-15T10:00:07Z",
      "participant": {
        "participant_id": "human:owner",
        "participant_kind": "human"
      },
      "target": {
        "entities": ["bath"],
        "spaces": ["arrival_area"],
        "patch_id": "patch_arrival_bath_move_001",
        "viewport": "onsen_live_root_viewport"
      },
      "raw": {
        "kind": "text",
        "text": "The bath is visible now, but the entrance still feels crowded."
      },
      "normalized": {
        "issue": "visual_density_too_high",
        "desired_direction": "increase_walkway_clearance",
        "semantic_axes": ["readability", "navigation", "arrival_identity"],
        "confidence": 0.82
      },
      "verification_relation": {
        "changes_world_verdict": false,
        "related_verification_event_id": "evt_verify_patch_001"
      }
    }
  ],
  "verification_page": {
    "schema": "agent_bridge.lswr.verification_page.v0",
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "cursor_next": null,
    "verifications": [
      {
        "event_id": "evt_verify_patch_001",
        "verification_id": "verify_patch_arrival_bath_move_001",
        "patch_id": "patch_arrival_bath_move_001",
        "verdict": "not_verified",
        "reason": "expected_effect_clause_failed",
        "failed_clause_ids": ["effect_walkway_clearance_001"]
      }
    ]
  },
  "presentation_page": {
    "schema": "agent_bridge.lswr.presentation_page.v0",
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "cursor_next": null,
    "presentations": [
      {
        "event_id": "evt_presentation_changed_001",
        "patch_id": "patch_arrival_bath_move_001",
        "render_refreshed": true,
        "visible_change": true,
        "change_markers": ["bath"],
        "human_visible_disturbance": {
          "flicker_frames": 0,
          "camera_jitter": false
        }
      }
    ]
  },
  "interaction_state_after": {
    "schema": "agent_bridge.lswr.interaction_state.v0",
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "tick": 1208,
    "authority_mode": "coedit",
    "active_view": {
      "viewport": "onsen_live_root_viewport",
      "camera": "main",
      "selected_entities": ["bath"],
      "active_space": "arrival_area"
    },
    "latest_event_id": "evt_ai_patch_proposed_002",
    "latest_feedback_id": "fb_arrival_crowded_001",
    "latest_verification_id": "verify_patch_arrival_bath_move_001",
    "presentation_status": {
      "render_fresh": true,
      "visible_change_markers": ["bath"],
      "human_visible_disturbance": {
        "measured": true,
        "flicker_frames": 0
      }
    }
  },
  "expected_agent_readback": {
    "selected_entities": ["bath"],
    "latest_visible_change": "patch_arrival_bath_move_001",
    "latest_verification_verdict": "not_verified",
    "latest_verification_reason": "expected_effect_clause_failed",
    "failed_clause_ids": ["effect_walkway_clearance_001"],
    "latest_human_decision": "reject",
    "latest_feedback_issue": "visual_density_too_high",
    "next_revision_patch_id": "patch_arrival_bath_move_002",
    "revision_should_cite": [
      "verify_patch_arrival_bath_move_001",
      "fb_arrival_crowded_001"
    ]
  },
  "acceptance_assertions": [
    "human_select_is_event_addressable",
    "ai_patch_has_reason_expected_effect_and_rollback_group",
    "presentation_visible_change_is_separate_from_patch_result",
    "verification_not_verified_survives_human_reject",
    "raw_feedback_survives_normalization",
    "revision_patch_cites_failed_verification_and_feedback",
    "primary_readback_requires_no_screenshot"
  ]
}
```

## 3. Readback Expectations

An AI agent should be able to answer the following from the fixture without
screenshot evidence:

| Question | Expected answer |
|---|---|
| What did the human focus on? | `bath` in `arrival_area` |
| What did the AI try? | Move `bath` from `[2, 3]` to `[4, 3]` |
| Did the runtime apply the patch? | yes, `runtime.patch_result.applied=true` |
| Did the presentation visibly change? | yes, `presentation.state_changed.visible_change=true` |
| Did the expected effect pass? | no, `expected_effect_clause_failed` |
| Which clause failed? | `effect_walkway_clearance_001` |
| Did the human accept it? | no, `human.reject` |
| What did the human say? | "The bath is visible now, but the entrance still feels crowded." |
| What should the AI do next? | propose a revision that preserves visibility and increases walkway clearance |

## 4. Acceptance Mapping

| Protocol falsifier | Fixture evidence |
|---|---|
| `IFP1` | `human.select`, `feedback.explicit_text`, and `human.reject` carry entity, space, viewport, patch, and raw text refs |
| `IFP2` | `runtime.patch_result` and `presentation.state_changed` are separate records |
| `IFP3` | `verification.verdict="not_verified"` remains unchanged after `human.reject` |
| `IFP4` | explicit text feedback has raw text, normalized issue, and confidence |
| `IFP5` | second AI patch cites both `verify_patch_arrival_bath_move_001` and `fb_arrival_crowded_001` |
| `IFP6` | this fixture has one AI editor; future multi-agent fixtures can add critic feedback without patch authority |

## 5. Boundaries

This fixture does not:

- implement an event store;
- register MCP tools;
- invoke or patch a live runtime;
- write memory;
- ingest #94 outcomes;
- open `dry_run=false`;
- claim default-profile exposure;
- require screenshots for primary readback.

## 6. Recommended Next Work

Next implementation should remain read-only:

1. Move this JSON fixture into a test fixture file.
2. Add a pure validator that checks:
   - event ID uniqueness;
   - referenced cause events exist;
   - patch IDs chain correctly;
   - failed verification survives human review;
   - revision patches cite both failed verification and feedback.
3. Add a report formatter that produces the readback table in section 3.
4. Keep any MCP exposure all-profile/niche until accepted.
