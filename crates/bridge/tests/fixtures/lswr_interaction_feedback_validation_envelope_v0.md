# LSWR Interaction Feedback Validation

- schema: `agent_bridge.lswr.interaction_feedback_validation_envelope.v0`
- fixture_schema: `agent_bridge.lswr.interaction_feedback_fixture.v0`
- validation_schema: `agent_bridge.lswr.interaction_feedback_validation.v0`
- readback_schema: `agent_bridge.lswr.interaction_feedback_readback.v0`
- readback_mode: `interaction_feedback_detailed`
- valid: `true`
- failure_reasons: `none`
- requires_screenshot_for_primary_readback: `false`

## Guardrails

- read_only: `true`
- mutation_surface: `none`
- writes_state: `false`
- store_access_required: `false`
- mcp_tool_registered: `false`
- primary_readback_requires_screenshot: `false`
- feedback_changes_world_verdict_allowed: `false`

## Readback

- selected_entities: `bath`
- latest_visible_change: `patch_arrival_bath_move_001`
- latest_verification_verdict: `not_verified`
- latest_verification_reason: `expected_effect_clause_failed`
- failed_clause_ids: `effect_walkway_clearance_001`
- latest_human_decision: `reject`
- latest_feedback_issue: `visual_density_too_high`
- next_revision_patch_id: `patch_arrival_bath_move_002`
- revision_should_cite: `verify_patch_arrival_bath_move_001, fb_arrival_crowded_001`

## Next Agent Action Contract

- preserve_failed_world_verdict: `true`
- treat_human_feedback_as_revision_input: `true`
- require_revision_sources_from_readback: `true`
- forbid_ingestion_or_state_write: `true`
