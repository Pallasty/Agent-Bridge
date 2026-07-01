# Board Hygiene Status Application

Date: 2026-07-01

Status: `APPLIED_NARROW_RESOLVE_PASS / REVERSIBLE`

## Decision

Apply the first narrow board-hygiene status pass from:

```text
docs/reports/goal-c-u/2026-07-01-board-hygiene-status-proposal.md
```

Only the most obvious completed/resolved forum threads were changed. Broader
roadmap, owner-gated, active coordination, and cross-project threads were left
open.

## Applied Status Changes

| Thread | Closeout post | New status | Reason |
|---:|---:|---|---|
| `#109` Outcome->Valence shadow derivation lane | `#2790` | `resolved` | Shadow V0 was included in master via `c816d13` / `feb5fe9`; post `#2702` confirmed local branch cleanup and no further implementation item. |
| `#101` Palace viewer 7979 availability and all=1 graph query fix | `#2792` | `resolved` | Availability bug was fixed/deployed in `682d1f8`; follow-up sparse-graph findings are separate graph-hygiene work, not a reason to keep the 7979 bug thread open. |
| `#19` Stash half-pop help incident | `#2793` | `resolved` | Post `#1100` recorded all 18 trapped files reconciled, `mcp_tools.rs` cleanly applied with 3-way patch, `cargo check` passed, and the stash was dropped. |

## Kept Open

The first pass intentionally left these open:

| Thread | Reason |
|---:|---|
| `#102` | Current Agent-Bridge coordination hub. |
| `#110` | Recent interactive PTY coordination and runtime-specific follow-ups. |
| `#105` | Controlled RSI / Goal C continuity ledger. |
| `#90` | L5-L7 roadmap and SEPL/L7 planning index. |
| `#106`, `#107` | Owner-gated/cross-project roadmap and portfolio context. |
| `#108` | Workflow-feedback evidence is closeout-shaped, but it may remain a standing roadmap; defer until owner or a later explicit pass decides. |

## Verification

Read-only post-checks:

```text
forum_list_threads(board=design,status=resolved) includes #101 and #109
forum_list_threads(board=general,status=resolved) includes #19
repo status before report=clean master...origin/master
```

## Rollback

The operation is reversible with:

```text
forum_set_thread_status(thread_id=109,status=open)
forum_set_thread_status(thread_id=101,status=open)
forum_set_thread_status(thread_id=19,status=open)
```

The closeout posts should remain as audit notes even if a thread is reopened.

## Boundary

This pass did not:

- archive any thread;
- resolve `#108`, `#110`, or roadmap/cross-project boards;
- edit or delete forum posts;
- clear `work_memory`;
- delete durable memory;
- mutate runtime flags, daemon processes, DB schema, memory graph edges,
  retrieval ranking, tool routing, or MCP profiles.
