# LSWR Read-Only Bridge Report

report_schema: agent_bridge.lswr.readonly_bridge_report.v0
summary_schema: agent_bridge.lswr.readonly_bridge_consumer_summary.v0
projection_schema: agent_bridge.lswr.readonly_bridge_snapshot.v0
snapshot_sha256: sha256:5ff171f505327b9d93f01a1dfc44a6159a00f48e6085a5e7a63e5eded6629495
readback_mode: detailed_snapshot
read_only_confirmed: true

## Safety
- read_only: true
- mutation_surface: none
- mcp_tool_registration: false
- affordances: snapshot=true, query=true, patch=false, action=false, invoke=false

## Counts
- actions: 1
- events: 2
- verifications: 1
- feedback: 1
- rollback_records: 1

## Query Surfaces
- world.actions.query
- world.events.query
- world.evidence.query
- world.feedback.query
- world.rollbacks.query

## Verification Outcomes
- verified: 1
- not_verified: 0
- blocked: 0
- feedback_changes_world_verdict: 0

## Verified
- action: action:move_cube_readonly_fixture; verdict: verified; method: semantic_state_query; target: entity=entity:cube_readonly_fixture; raw_available: true
- evidence: semantic_scene/semantic_state_query - semantic state reports the expected transform

## Not Verified
- none

## Blocked
- none

## Feedback
- feedback: feedback:readonly_bridge_fixture_accept; source_event: event:move_cube_readonly_fixture_accept; decision: accept; changes_world_verdict: false
- targets: entities=entity:cube_readonly_fixture, actions=action:move_cube_readonly_fixture, events=event:move_cube_readonly_fixture_result, rollback_groups=rollback:move_cube_readonly_fixture

## Rollbacks
- rollback_group: rollback:move_cube_readonly_fixture; actions: action:move_cube_readonly_fixture; verification_event_id: event:move_cube_readonly_fixture_result

## Guidance
- Verified items come from adapter or runtime evidence only.
- Human feedback remains feedback and must not alter verification verdicts.
- Rollback records describe reversible before and after state; this summary does not execute rollback.
