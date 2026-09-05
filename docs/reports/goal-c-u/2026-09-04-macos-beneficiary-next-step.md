# Mac runtime review and beneficiary next step

Decision: KEEP_CURRENT_RUNTIME. This is a bounded local observation, not a
deployment, security certification, or change to the active decision board.

## Observed on 2026-09-04

- The clean review worktree starts at `24a38bf2e70cb594bdc3d8f494dc9ea4776d6ad2`.
- Installed binary and connected MCP report `cd219d57d3b1`.
- daemon-http listens on loopback ports 7878/8799 and the current Tailscale IPv4
  address on 7878; Palace listens on loopback port 7979.
- `tailscale debug netmap` exposes an effective packet filter accepting TCP
  across all ports from broad tailnet ranges and an advertised private subnet.
  This establishes a broad network trust boundary, not anonymous Internet access.
- `tailscale status --json` shows seven visible peers, all with the same UserID
  as this node. This is a current visibility snapshot, not a complete account,
  device-compromise, or control-plane ACL audit. No peer write was attempted.
- The state directory is owned by the current user with mode 0700; the database
  is mode 0644. Directory traversal restricts ordinary other-user access through
  this path. This does not audit backups, alternate links, privileged access, or
  every filesystem access mechanism.

The broad packet filter warrants an accurate description of the trusted fleet,
but does not establish misuse or justify disabling the existing cross-device
workflow. No demonstrated local incident requires the broad master deployment
previously rejected by the runtime-alignment preflight. No listener, ACL,
permission, database, or service was changed.

## First-user priorities

The Agent needs a correct continuation more often than another capability:
one intended worktree, current commitment, last verified outcome, outstanding
uncertainty, and next useful action. The current task repeatedly recovered the
dirty primary checkout instead of the clean integration surface. Use the
existing scoped work-memory and task handoff surfaces to preserve that working
context; do not add a second registry or a new recovery service.

Authorization already given for the same action should survive a continuation.
Ask at a material new boundary, and explain actual drift when a previous grant
no longer applies. Do not turn every command or recoverable correction into a
new approval ceremony.

Semantic perception should answer a task's question through existing AX/window
state and bounded changes. Screenshots, voice, and mobile projection are useful
when they add information or expression for that task; their invocation count
is not a measure of embodiment benefit.

## Next useful task

On the next naturally resumed development task, use the existing handoff to
recover its worktree and commitment and complete its concrete postcondition.
Note only an observed missing/stale/harmful recall, unnecessary repeated
authorization, or failed recovery. Reuse existing evidence and do not count
this review as a new independently verified north-star sample.

If no such defect occurs, continue ordinary useful work. If one occurs, correct
the smallest existing surface responsible and verify against that same task.
R4/R7 remain within their current admitted use; R9/Guardian/R10 expansion stays
subject to the active decision board. No new deployment gate is created here.

## Continuation follow-through

On the next continuation, project-scoped `work_memory list` returned no rows.
The conversation summary, followed by Git inspection, recovered this worktree
and its two pending documentation changes. This does not establish a retrieval
bug: the previous turn had not recorded an active handoff in this surface.

The existing `macos-beneficiary-continuation` work-memory slot was saved under
the primary project scope and read back successfully. It names the isolated
worktree, branch/base, owned files, next action, and the boundary between local
work and production changes. No new memory store or runtime code was needed.
The immediate outcome is a recoverable documentation change and a discoverable
publication handoff. A same-turn save/get is not a cross-session acceptance test
and does not qualify as an independently verified continuity success.
