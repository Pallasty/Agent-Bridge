# Active Work Memory And Board Staleness Audit

Date: 2026-07-01

Status: `READ_ONLY_AUDIT / NO_WORK_MEMORY_CLEAR / NO_BOARD_STATUS_CHANGE`

## Decision

Do not clear or delete any `work_memory` rows in this slice.

The correction co-surface lane is now closed through S1, but several older
project-scoped `work_memory` rows still advertise completed or superseded
sub-lanes as active. This report records the current state so future sessions do
not mistake those rows for open implementation work.

## Scope

Store:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Project scope:

```text
project:/Data/CascadeProjects/agent-bridge
```

Read-only queries covered:

- active `kind=work_memory` rows in the Agent-Bridge project scope;
- most recently active forum threads by `last_post_at`;
- current git head and worktree state.

No `work_memory clear`, `memory_delete`, board status update, or runtime change
was performed.

## Findings

Active project-scoped `work_memory` rows:

| Class | Count |
|---|---:|
| stale-complete-or-superseded | 12 |
| active-policy | 1 |
| active/unclear | 6 |
| total | 19 |

The most important stale/superseded rows are:

| Key | Status line | Why it is stale or superseded |
|---|---|---|
| `work_memory_3d56857a5eed_shared_active` | `closed-s1-pass-no-s2` | current shared slot says correction co-surface is closed; it should not be treated as an open next action |
| `work_memory_3d56857a5eed_codex-correction-cosurface-ab-gate-20260701_active` | `packet-pushed-owner-gate-open` | superseded by S1 pass and final closeout through `dd88a74` |
| `work_memory_3d56857a5eed_codex-correction-cosurface-shadow-20260701_active` | `done-next-gate-controlled-ab-window` | superseded by copied-DB MCP A/B and live-store S1 pass |
| `work_memory_3d56857a5eed_codex-correction-cosurface-backfill-20260701_active` | `done-next-gate-cosurface-ab` | backfill is completed and must not be repeated |
| `work_memory_3d56857a5eed_codex-correction-cosurface-preflight-20260701_active` | `completed` | superseded by completed backfill and S1 closeout |
| `work_memory_3d56857a5eed_codex-open-queue-staleness-20260701_active` | `completed` | superseded by newer queue and S1 closeouts |
| `work_memory_3d56857a5eed_codex-workflow-feedback-usage-20260701_active` | `completed` | useful evidence, but not an open implementation lane |
| `work_memory_3d56857a5eed_codex-centrality-no-go-20260701_active` | `done` | durable NO-GO reference, not active work |

The active policy row is still useful:

```text
work_memory_3d56857a5eed_codex-standing-reversible-authorization-20260701_active
```

It records the standing authorization contract for reversible operations and
should remain visible.

## Board Snapshot

Most recently active forum threads:

| Thread | Status | Interpretation |
|---|---|---|
| #102 `AB borrowed-patterns landing kanban - 2026-06-09` | open | current coordination thread; latest posts close correction co-surface S1 |
| #108 `Workflow feedback loop research landing and next AB slice` | open | viable read-only next lane if more workflow-feedback evidence is needed |
| #110 `交互 PTY 扇出...` | open | coordination thread; do not touch without reading current owner context |
| #105 `Agent-Bridge Controlled RSI / Goal C continuity honest ledger` | open | broad continuity ledger; useful for planning, not a single open implementation task |

Older open design threads remain useful context but should not be interpreted as
fresh owner asks without a new post or active `work_memory` update.

## Recommendation

For the current session:

1. Treat correction co-surface as closed at S1 PASS and keep long-lived live
   co-surface disabled.
2. Do not escalate to S2 without a new packet that records start/stop window,
   process ids, top-k diff capture, and rollback.
3. Use the next reversible lane for one of:
   - workflow-feedback evidence on a completed lane;
   - a docs-only stale-board cleanup proposal;
   - an isolated read-only preflight audit.

For a future cleanup slice:

1. Create a small allowlist of `work_memory` keys to clear.
2. Back up or export those rows first.
3. Use `work_memory clear` only for rows whose durable report/memory/forum
   closeout exists.
4. Leave the standing authorization policy row active.

## Boundary

This report did not:

- clear active `work_memory`;
- delete memory rows;
- change forum thread status;
- run S2;
- enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in long-lived processes;
- change code or runtime behavior.
