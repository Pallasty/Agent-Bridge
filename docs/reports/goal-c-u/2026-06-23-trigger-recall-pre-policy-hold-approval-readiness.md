# Trigger Recall Pre-Policy Hold Approval Readiness

Date: 2026-06-23

Scope: docs-only approval-readiness review for
`trigger_recall_opt_in_pre_policy_hold_simulation`. This document does not
implement runtime code, does not authorize production `enforce_hold`, does not
change default `memory_search`, does not register an MCP tool, does not deploy,
and does not write memory or graph state.

## Verdict

`APPROVAL-PROCESS-GAP`.

The current proposal chain is intentionally conservative, but it now contains
an approval-order deadlock:

1. runtime implementation is `NO-GO` until an approval packet names an exact
   implementation commit;
2. an exact implementation commit cannot exist unless candidate code is first
   written somewhere.

Do not resolve this by weakening the exact-commit approval packet. Keep that
packet as the merge/runtime gate. Instead, split the process into two gates.

## Two-Stage Gate

### Stage 1: Candidate-Work Authorization

Purpose: allow a candidate commit to be produced in an isolated worktree or
branch.

Allowed:

- create an isolated worktree or branch;
- implement `trigger_recall_opt_in_pre_policy_hold_simulation` as candidate
  code;
- add tests and docs;
- run local verification.

Forbidden:

- merge to `master`;
- deploy;
- change default `memory_search`;
- expose the tool outside `Tier::Niche`;
- treat the candidate as approved runtime behavior;
- production `enforce_hold`.

Required stage-1 packet fields:

| Field | Required |
|---|---|
| `authorization_kind` | `candidate_work_only` |
| `approved_mode` | `pre_policy_hold_simulation_candidate` |
| branch/worktree | exact branch and path |
| allowed files | exact file list |
| forbidden behavior | default search change, deploy, merge, production hold |
| rollback | discard branch/worktree |
| reviewer | non-empty |
| forum post id | board-visible |

Stage 1 does not need an implementation commit because its purpose is to allow
one to be created. It must still name the exact files and branch/worktree.

### Stage 2: Exact-Commit Approval Packet

Purpose: decide whether a specific candidate commit may be merged or used for
runtime simulation.

Required:

- exact implementation commit;
- exact approved mode: `pre_policy_hold_simulation`;
- regression results;
- redaction proof;
- fail-open proof;
- operator disable proof;
- default `memory_search` unchanged proof;
- board-visible reviewer decision;
- expiry/freshness policy.

Stage 2 remains the only gate that can approve merge/runtime behavior.

## Current State

Current synced head:

```text
2709a0a docs(memory): propose trigger pre-policy hold simulation
```

Relevant docs:

- `2026-06-23-trigger-recall-enforce-hold-approval-packet-schema.md`
- `2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`
- `2026-06-23-trigger-recall-pre-policy-hold-schema-review.md`
- `2026-06-23-trigger-recall-pre-policy-hold-implementation-proposal.md`

Current implementation authority:

| Action | State |
|---|---|
| write runtime candidate in isolated worktree | needs Stage 1 authorization |
| merge runtime candidate | needs Stage 2 exact-commit approval |
| deploy runtime candidate | needs Stage 2 exact-commit approval |
| production `enforce_hold` | still `NO-GO` |
| default `memory_search` change | still `NO-GO` |

## Recommended Stage-1 Packet Shape

```text
Decision: APPROVED-FOR-CANDIDATE-WORK-ONLY
Mode: pre_policy_hold_simulation_candidate
Branch: codex/trigger-pre-policy-hold-simulation-candidate
Worktree: /Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate
Allowed files:
- crates/bridge/src/trigger_recall_opt_in.rs
- crates/bridge/src/mcp_tools.rs
- docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-simulation.md
Forbidden:
- merge to master
- deploy
- default memory_search change
- production enforce_hold
- non-Niche exposure
Rollback: remove worktree/branch
Expires: <date>
```

Without a Stage-1 packet, runtime candidate work remains blocked.

## Next Safe Action

Ask for or create a board-visible Stage-1 candidate-work authorization packet.
If approved, create a new worktree and implement there. Do not implement in the
main checkout while unrelated probe files or parallel work may be present.
