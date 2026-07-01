# Work Memory Stale Active Clearance

Date: 2026-07-01

Status: `CLEARED / VERIFIED`

## Decision

Clear only session-scoped `work_memory` rows that are already completed,
superseded, and backed by durable repo/forum/memory evidence.

This cleanup does not change runtime behavior, forum thread status, memory
records, ranking logic, daemon state, environment flags, or the project shared
active slot.

## Scope

Store:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Project scope:

```text
project:/Data/CascadeProjects/agent-bridge
```

Repo head before cleanup:

```text
fedaf29 docs(workflow): add cosurface latch feedback evidence
```

Current worktree before cleanup:

```text
## master...origin/master
```

## Keep Active

These rows remain active:

| Key | Reason |
|---|---|
| `work_memory_3d56857a5eed_shared_active` | current shared project slot; it points at workflow-feedback cosurface evidence and is the right place for current continuity |
| `work_memory_3d56857a5eed_codex-standing-reversible-authorization-20260701_active` | standing reversible-operations authorization policy; still needed for planning and gate interpretation |

The shared active row before cleanup said:

```text
status: pushed-readonly-evidence
summary: Added and pushed a workflow-feedback Experience Object fixture for the
correction co-surface S1 pass plus a held-out scenario and report.
evidence: commit c1099fe; report
docs/reports/goal-c-u/2026-07-01-workflow-feedback-correction-cosurface-experience.md
```

The standing authorization row before cleanup said:

```text
status: active-policy
summary: reversible operations may proceed with an explicit rollback plan,
backup where relevant, bounded blast radius, and post-check.
boundary: still pause for irreversible/destructive actions, credential/secrets
exposure, external monetary/legal commitments, or operations whose rollback
cannot be demonstrated.
```

## Clear Allowlist

These rows are safe to clear because they advertise completed or superseded
session lanes as active:

| Key | Pre-clear status | Durable closeout |
|---|---|---|
| `work_memory_3d56857a5eed_codex-correction-cosurface-preflight-20260701_active` | `completed` | correction backfill reports and queue closeout through `3b36033`; later S1 pass through `dd88a74` |
| `work_memory_3d56857a5eed_codex-correction-cosurface-backfill-20260701_active` | `done-next-gate-cosurface-ab` | single-edge live backfill complete; later S1 pass through `dd88a74` |
| `work_memory_3d56857a5eed_codex-open-queue-staleness-20260701_active` | `completed` | stale queue audit superseded by later queue, S1, and workflow-feedback closeouts |
| `work_memory_3d56857a5eed_codex-correction-cosurface-ab-gate-20260701_active` | `packet-pushed-owner-gate-open` | A/B packet superseded by copied-DB smoke, env-gate unit coverage, and S1 pass |
| `work_memory_3d56857a5eed_codex-correction-cosurface-shadow-20260701_active` | `done-next-gate-controlled-ab-window` | shadow diff superseded by copied-DB MCP A/B and S1 pass |
| `work_memory_3d56857a5eed_codex-workflow-feedback-usage-20260701_active` | `completed` | usage evidence is durable in repo; newer workflow-feedback evidence landed at `c1099fe` and `fedaf29` |
| `work_memory_3d56857a5eed_codex-centrality-no-go-20260701_active` | `done` | centrality NO-GO is durable in repo/forum/memory and should not remain an active lane |

## Export Backup

Before clearing, each allowlisted row was read with `work_memory get
compact=false`. The essential pre-clear row content is preserved below.

### Correction Co-Surface Preflight

```text
key: work_memory_3d56857a5eed_codex-correction-cosurface-preflight-20260701_active
title: Correction co-surface single-edge backfill completed
status: completed
summary: correction co-surface single-edge live-store backfill is complete and
documented; queue closeout commit 3b36033 was pushed; no env enablement, daemon
restart, deploy, schema change, ranking change, or extra live write was done.
next_step: do not repeat the correction backfill; only a separate owner-approved
A/B or shadow enablement window could follow.
evidence: backup state.before-correction-edge-backfill.20260701T114243.db,
sha256 9da1a973af97d89d86d90ffa8e8bbb115fa9d6c5bbdb14303b73604892789174;
missing_valid_correction_edges=[]; no visible
AGENT_BRIDGE_CORRECTION_COSURFACE env.
files:
- docs/reports/goal-c-u/2026-07-01-correction-cosurface-live-backfill-preflight.md
- docs/reports/goal-c-u/2026-07-01-correction-cosurface-single-edge-backfill.md
- docs/reports/goal-c-u/2026-07-01-agent-bridge-open-queue-staleness-audit.md
```

### Correction Co-Surface Backfill

```text
key: work_memory_3d56857a5eed_codex-correction-cosurface-backfill-20260701_active
title: Correction co-surface backfill done
status: done-next-gate-cosurface-ab
summary: owner-approved one-row live corrects edge backfill executed, verified,
and pushed through queue closure commit 3b36033.
next_step: do not repeat the backfill; any later gate needs a separate bounded
A/B or shadow window with AGENT_BRIDGE_CORRECTION_COSURFACE=1 and top-k diffs.
evidence: corrects edges 4 -> 5, missing_valid_correction_edges=[]; same
backup and sha256 as preflight; repo pushed to origin/master at 3b36033.
files:
- docs/reports/goal-c-u/2026-07-01-correction-cosurface-single-edge-backfill.md
- docs/reports/goal-c-u/2026-07-01-agent-bridge-open-queue-staleness-audit.md
```

### Open Queue Staleness

```text
key: work_memory_3d56857a5eed_codex-open-queue-staleness-20260701_active
title: Agent-Bridge open queue staleness audit current after correction backfill
status: completed
summary: open queue audit reflected master after PR #32 merge, Kilo first-prompt
fix, correction co-surface link review, centrality NO-GO, and completed
single-edge backfill.
next_step: if no owner gate opens, use read-only work such as workflow-feedback
usage evidence, report-quality improvement, stale-board cleanup proposals, or
isolated preflight audits.
evidence: commit 3b36033 updated
docs/reports/goal-c-u/2026-07-01-agent-bridge-open-queue-staleness-audit.md.
```

### Correction Co-Surface A/B Gate

```text
key: work_memory_3d56857a5eed_codex-correction-cosurface-ab-gate-20260701_active
title: Correction co-surface A/B gate packet landed
status: packet-pushed-owner-gate-open
summary: docs-only owner gate packet for S1 correction co-surface controlled
A/B landed and pushed; no runtime env was enabled.
next_step: wait for owner/board approval before running S1 with
AGENT_BRIDGE_CORRECTION_COSURFACE=1; otherwise continue autonomous read-only/docs
lanes.
evidence: commit 4880d63 and report
docs/reports/goal-c-u/2026-07-01-correction-cosurface-ab-enablement-packet.md.
```

### Correction Co-Surface Shadow

```text
key: work_memory_3d56857a5eed_codex-correction-cosurface-shadow-20260701_active
title: Correction co-surface shadow diff complete
status: done-next-gate-controlled-ab-window
summary: read-only default-FTS shadow diff ran after the single-edge backfill;
original-focused queries inserted correction at rank 2, correction-focused
queries already ranked correction first, and exclude_kinds guardrail stayed
unchanged.
next_step: only run controlled A/B/shadow with env enabled if owner approves;
do not broad-enable by default from this report alone.
evidence: commit 94ea29d and report
docs/reports/goal-c-u/2026-07-01-correction-cosurface-shadow-diff.md.
```

### Workflow Feedback Usage

```text
key: work_memory_3d56857a5eed_codex-workflow-feedback-usage-20260701_active
title: Workflow feedback runbook usage evidence recorded
status: completed
summary: workflow-feedback low-risk promotion runbook was replayed on current
master and docs-only usage evidence recorded; report, shadow-score, owner-review
packet, and promotion-record commands succeeded.
next_step: continue read-only workflow-feedback usage evidence on future
completed lanes or stale-board cleanup proposals; do not treat this as
runtime/retrieval/tool-routing authorization.
evidence: commit d1f0820 and report
docs/reports/goal-c-u/2026-07-01-workflow-feedback-runbook-usage-evidence.md.
```

### Centrality NO-GO

```text
key: work_memory_3d56857a5eed_codex-centrality-no-go-20260701_active
title: Centrality prior NO-GO consolidated
status: done
summary: offline PageRank/global centrality prior evaluation was consolidated as
NO-GO; final origin/master was clean after the centrality and Kilo first-prompt
docs commits at that time.
next_step: use the NO-GO as a blocker if centrality/PageRank ranking prior
reappears; next useful lane is owner-gated semantic ranking-weight validation or
query-local repair.
evidence: commit 230121f, forum #102 post #2752, and memory
centrality_prior_offline_no_go_repo_record_20260701.
files:
- docs/reports/goal-c-u/2026-07-01-centrality-prior-offline-no-go.md
- docs/DESIGN-memory-search-ranking-2026-05-23.md
```

## Rollback Boundary

This cleanup is reversible enough for the standing authorization policy because:

- the row contents were exported above before clear;
- each row is a session scratchpad, not durable project memory;
- authoritative evidence remains in committed reports, forum posts, and durable
  memory;
- restoring any row would be a `work_memory save` using the exported content.

Do not use this report as authorization to delete durable memory rows, close
forum threads, mutate runtime flags, or rerun the correction backfill.

## Post-Clear Verification

Completed.

Actions performed:

- read and exported all 7 allowlisted rows before clearing;
- ran `work_memory clear` on each allowlisted key;
- reran `work_memory get` for each cleared key;
- confirmed all 7 returned `work memory key not found`;
- reran compact `work_memory list` for the project.

Cleared keys verified absent:

```text
work_memory_3d56857a5eed_codex-correction-cosurface-preflight-20260701_active
work_memory_3d56857a5eed_codex-correction-cosurface-backfill-20260701_active
work_memory_3d56857a5eed_codex-open-queue-staleness-20260701_active
work_memory_3d56857a5eed_codex-correction-cosurface-ab-gate-20260701_active
work_memory_3d56857a5eed_codex-correction-cosurface-shadow-20260701_active
work_memory_3d56857a5eed_codex-workflow-feedback-usage-20260701_active
work_memory_3d56857a5eed_codex-centrality-no-go-20260701_active
```

Rows intentionally retained:

```text
work_memory_3d56857a5eed_shared_active
work_memory_3d56857a5eed_codex-standing-reversible-authorization-20260701_active
```

Concurrent update observed and preserved:

```text
work_memory_3d56857a5eed_shared_active
status: verified-recorded
summary: workflow-feedback cosurface/latch fixtures and report verified on
origin/master@fedaf29, with forum #108 post #2778 and memory
workflow_feedback_cosurface_latch_evidence_20260701.
```

No durable memory row, forum thread status, runtime flag, daemon process, DB
schema, ranking behavior, or repository code path was changed by this cleanup.
