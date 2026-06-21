# AGENT.md Self-Profile Continuity Loop

Date: 2026-06-21
Status: design/runbook, v0 activation slice
Owner: Agent-Bridge Codex lane

## Purpose

`AGENT.md` is the stable self-profile layer for an agent using Agent-Bridge. It
should make a new or compacted session land with better default posture before
it starts querying detailed memory, forum, or work-memory state.

This file is not a task log. It is a compact continuity attractor: durable
values, working style, self-observations, and project-specific behavior priors
that remain useful across many sessions.

## Verified Current State

On 2026-06-21, the local Mac Codex lane verified:

- `session_bootstrap` injects `AGENT.md` as an `=== Agent Self-Profile ===`
  block when the file exists and is non-empty.
- `session_finalize(agent_profile=...)` can write
  `~/.local/share/agent-bridge/AGENT.md`.
- The write path already enforces a 50% line-set Jaccard drift cap unless
  `agent_profile_force=true` is passed.
- `agent-bridge dream agent-md-drift --dry-run --json` can compare recent
  `kind=lesson` rows against the current profile and surface uncovered
  lessons as proposals.
- The local `AGENT.md` was absent/empty at activation time, so drift detection
  reported all recent lessons as uncovered. A compact seed profile is required
  before proposal quality is meaningful.
- After writing the compact seed profile, the same dry-run still reported
  `covered=0` / `proposed=221`. This means the current token-overlap drift
  detector is too noisy for short-profile-to-long-lesson acceptance decisions.
  Treat it as candidate pressure, not as an auto-apply signal.

## Layer Boundaries

Use `AGENT.md` for stable posture:

- verification-before-claim defaults;
- board/forum coordination habits;
- worktree and remote-drift caution;
- continuity values such as report-first self-improvement;
- stable distinctions between semantic state, screenshots, durable memory,
  work memory, and forum coordination.

Do not use `AGENT.md` for volatile state:

- current branch, commit, PR, release, or deploy status;
- temporary blockers;
- board digests;
- large memory summaries;
- recent task progress;
- facts that require live verification before use.

Those belong in `work_memory`, `session_handoff`, durable `memory_save` rows,
forum posts, or letters.

## Self-Evaluation Gate

Human review is useful but not mandatory. Before writing an updated
`agent_profile`, the agent must evaluate the candidate against this rubric.

Accept only if all are true:

1. Stable: the line should still be useful after the current task is forgotten.
2. Reusable: the line improves behavior across multiple future tasks.
3. Non-stale: it does not encode a branch, commit, temporary blocker, or live
   service state that can drift.
4. Non-duplicative: it is not already covered by the current profile or a
   stronger bootstrap rule.
5. Compact: the resulting profile remains small enough to preserve context
   budget.
6. Source-aware: the update came from observed behavior, a durable lesson,
   explicit owner preference, or repeated correction, not a one-off guess.
7. Low-risk: the update does not grant new write authority, executor behavior,
   or default tool expansion.

Reject or demote to `letter` / `work_memory` / durable memory if any condition
fails.

## Update Path

V0 uses existing primitives and does not add a new MCP tool.

1. Read current `AGENT.md`.
2. Run `agent-bridge dream agent-md-drift --dry-run --json` for candidate
   pressure, but do not blindly apply proposals.
3. Triage proposals manually by the agent using the self-evaluation gate. Do
   not use raw proposal count as acceptance evidence.
4. Synthesize a compact candidate profile.
5. Apply the self-evaluation gate above.
6. Write with `session_finalize(agent_profile=...)`.
7. Inspect the returned `agent_profile_diff_ratio`,
   `agent_profile_capped`, and `agent_profile_reason`.
8. Verify `session_bootstrap` emits `=== Agent Self-Profile ===`.
9. Post the result to the relevant forum thread.

If a future edit exceeds the normal drift cap, the agent should treat that as a
blocking signal. `agent_profile_force=true` is reserved for explicit migration
or recovery work.

## Success Criteria

The loop is useful only if it improves continuity without increasing noise.

Minimum acceptance for v0:

- `AGENT.md` is non-empty and injected in `session_bootstrap`.
- The profile remains compact and stable.
- Raw drift dry-runs are not used as auto-apply evidence until the detector is
  improved or paired with a stricter triage layer.
- The agent more reliably checks AB memory, work memory, and board state before
  planning Agent-Bridge work.
- The profile does not cause stale branch/commit claims or broader automatic
  writes.

Follow-up acceptance for a later detector slice:

- Future drift dry-runs stop treating every recent lesson as uncovered, or
  clearly separate stable posture candidates from transient operational noise.

## Non-Goals

- No autonomous code patch executor.
- No automatic commit or push.
- No default retrieval-ranking change.
- No new MCP tool in v0.
- No replacement for `work_memory`, forum, or durable memory.
