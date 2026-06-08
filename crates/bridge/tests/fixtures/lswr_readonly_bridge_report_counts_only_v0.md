# LSWR Read-Only Bridge Report

report_schema: agent_bridge.lswr.readonly_bridge_report.v0
summary_schema: agent_bridge.lswr.readonly_bridge_consumer_summary.v0
projection_schema: agent_bridge.lswr.readonly_bridge_snapshot.v0
snapshot_sha256: sha256:5ff171f505327b9d93f01a1dfc44a6159a00f48e6085a5e7a63e5eded6629495
readback_mode: counts_only
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
- verified: unknown
- not_verified: unknown
- blocked: unknown
- feedback_changes_world_verdict: unknown

## Verified
- none

## Not Verified
- none

## Blocked
- none

## Feedback
- none

## Rollbacks
- none

## Guidance
- Counts and query surfaces are safe to display.
- Detailed verification, feedback, and rollback readback requires include_snapshot=true.
