# Reversible Autonomy Task Replan

Date: 2026-07-01

Status: `AUTHORIZATION_REPLAN / AUTONOMOUS_LOW_RISK_SCOPE / NO_RUNTIME_CHANGE`

## Decision

Use the owner's standing authorization as the default operating rule:
reversible actions are autonomous, provided the agent records evidence and
lessons afterward.

This changes the practical planning posture for Agent-Bridge queue work:

- do not stop for permission before read-only probes, docs/report work,
  branch/commit/push work, durable-memory/forum coordination, or backed-up
  local reversible maintenance;
- do pause or prepare an explicit gate for actions that change shared live
  behavior, cannot be cleanly rolled back, publish externally, touch secrets, or
  widen blast radius across nodes/users.

## Authorization Read

Primary standing rule:

```text
operating_permission_reversible_autonomy_supreme_20260627
```

Operational meaning:

- "reversible => autonomous";
- backup first when data loss risk can be converted into rollback safety;
- record non-trivial autonomous actions as auditable memory or repo evidence.

Subordinate carve-out:

```text
agent_bridge_memory_authorization_contracts_20260625
correction:agent_bridge_memory_authorization_contracts_20260625:0c4795435f1b72ec
```

Operational meaning:

- subsystem runtime authority remains gated where it changes automatic graph,
  memory, ranking, search-order, or runtime-influence behavior;
- that contract does not block reversible operator-level work such as memory
  hygiene, backed-up local config, docs/branch work, and read-only probes.

## Current Queue Read

Current baseline before this report:

```text
94ea29d docs(memory): shadow correction cosurface diff
d1f0820 docs(workflow): record feedback runbook usage evidence
3b36033 docs(memory): close queue after correction backfill
```

Working tree was clean before this report.

Already closed or completed:

| Lane | Current state |
|---|---|
| Correction co-surface branch merge | Landed before this slice. |
| Single correction-edge backfill | Completed, backed up, read-only verified; do not repeat. |
| Correction co-surface shadow diff | Completed at `94ea29d`; positive targeted default-FTS evidence. |
| Workflow-feedback runbook usage replay | Completed at `d1f0820`; report, shadow-score, owner-review packet, and promotion-record commands replayed read-only. |
| Centrality/PageRank prior | Closed as NO-GO for ranking. |
| Kilo/opencode first-prompt readiness | Closed with deterministic coverage. |

Still gated:

| Lane | Gate |
|---|---|
| `AGENT_BRIDGE_CORRECTION_COSURFACE=1` live enablement | Runtime read-path behavior; use a separate controlled A/B or shadow window gate. |
| Bounded coactivation latch | Shared-store decay behavior; owner-reviewed implementation lane. |
| SQLite `VACUUM` | Maintenance window with writer freeze and backup. |
| Trigger recall production/default behavior | Explicit production packet only. |
| BioCortex/T6 runtime influence | Runtime-influence gate. |
| Workflow-feedback higher-blast scopes | Separate owner packet before retrieval, prompt, profile, tool-routing, skill, bootstrap, or runtime influence. |

## Selected Autonomous Scope

This slice implements only reversible coordination work:

1. Add this repo report so the authorization interpretation is durable.
2. Save durable memory for the workflow-feedback runbook usage evidence.
3. Update shared work memory to reflect the replan and current queue state.
4. Post forum updates to keep parallel units from repeating closed work.

This slice does not:

- enable `AGENT_BRIDGE_CORRECTION_COSURFACE`;
- restart daemons;
- deploy;
- write live DB rows;
- change schema;
- change default retrieval behavior;
- change ranking weights;
- change prompts/profiles/bootstrap/tool routing;
- install skills or plugins;
- alter secrets or credential handling.

## Next Operating Order

Use this order unless a newer owner instruction overrides it:

1. Continue autonomous read-only/docs/measurement work without asking for
   repeated permission.
2. Prefer lanes that produce reusable evidence: workflow-feedback usage
   samples, stale-board cleanup proposals, queue audits, and report quality
   improvements.
3. Convert risky local maintenance into reversible work by backing up first,
   then record the backup path and verification.
4. Escalate only when the action would change shared live behavior or crosses a
   named subsystem runtime gate.

## Boundary

This report records an authorization interpretation and a low-risk execution
plan. It is not approval for correction co-surface live enablement, production
retrieval changes, runtime influence, graph/ranking policy changes, broad live
DB writes, deployment, or cross-node cutover.
