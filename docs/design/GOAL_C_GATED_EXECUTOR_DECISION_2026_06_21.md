# Goal C Gated Executor Decision

Date: 2026-06-21

Plan: `ab_controlled_rsi_goal_c_20260621`, step G4.

Decision: do not build a dedicated approval-gated executor yet.

## Decision

Agent-Bridge should keep the controlled recursive self-improvement lane
report-first and surface-neutral for now.

Rejected for this phase:

- a self-improvement executor;
- a new MCP tool for `U`;
- runtime self-patching;
- automatic branch/patch/commit/push behavior;
- SEPL resource writes from this lane;
- memory or retrieval mutation as a side effect of `U`.

Allowed next:

- manual or scripted local `U` reports;
- docs/runbook refinement;
- consuming owner-lane recall and LSWR-H1 evidence after it lands;
- one future dry-run patch plan for a report helper, if recall metrics are
  trustworthy.

## Evidence

### G0-G3 State

- G0 landed controlled recursive self-improvement as governed, report-first, and
  non-self-patching.
- G1 landed the continuity honest ledger inventory.
- G2 landed the report-first `U` surface/runbook.
- G3 landed a dry-run patch plan for a future minimal report helper.

These are enough to define the direction. They are not enough to prove that an
executor will produce useful adopted actions.

### Board State

Thread #120 is the controlling board thread.

- #3736 accepted the governed/report-first framing and defined `U` as the
  standing utility surface.
- #3745 integrated LSWR-H1 onto a local current-baseline branch
  `codex/lswr-h1-heldout-probe-current-baseline`, commit `7f1efc1`, but it is
  not on current `master` and is not a run result.
- #3746 reported the first strong `U` finding: semantic recall on the Mac e5
  store is currently a negative continuity signal. The likely root causes are
  e5-small anisotropy/cosine saturation and stale mixed embedding rows.

### Mainline State

Current `master` is `8db6227`.

The LSWR-H1 current-baseline branch exists locally, but mainline does not yet
contain `7f1efc1`.

Therefore any executor would be premature: it would automate a loop whose core
measurement inputs are still settling.

## Why No Executor Yet

An executor is justified only when the report loop is repeatedly useful and the
actions are externally anchored.

Current blockers:

- `recall_eval` host/model selection is still a live owner-lane dependency.
- Semantic recall is currently worse than FTS on the Mac e5 store.
- The first `U` finding points to measurement and embedding-quality work, not to
  automation.
- LSWR-H1 has a design/integration branch but no accepted run result.
- No `U` report action has yet been adopted and measured after completion.
- Tool-surface contraction is a goal, so adding an executor surface would move
  against the current pressure unless there is repeated demand.

## Reconsideration Gate

Reconsider an approval-gated executor only after all conditions below hold:

1. At least one `U` report has produced an adopted action.
2. The adopted action has a before/after measurement.
3. The report includes an external anchor, falsifier, owner, and rollback path.
4. Recall metrics distinguish measured semantic recall from skipped/stale
   semantic recall.
5. LSWR-H1 is either run and classified, or explicitly absent/stale in the
   report.
6. Tool Atlas shows the executor would replace repeated manual work rather than
   expand unused surface area.
7. The executor design remains approval-gated and cannot commit, push, mutate
   memory, change retrieval order, or write SEPL resources without explicit
   owner authorization.

## Next Recommended Work

Do not continue this plan into code immediately.

Recommended next work is a successor stage:

1. Track the Mac/design-lead recall-eval host/model fix and semantic root-cause
   work from #3736/#3746.
2. When that lands, refresh the `U` report manually.
3. If the report proposes an action with a real external anchor, create a
   separate implementation plan for a local report helper.
4. Keep any helper outside MCP until repeated use proves it should be promoted.

## Plan Closure

This closes `ab_controlled_rsi_goal_c_20260621`.

The project has a controlled self-improvement framework:

- G0 design and board alignment;
- G1 honest continuity ledger;
- G2 report-first `U` surface;
- G3 dry-run patch plan;
- G4 executor rejection until evidence justifies it.

The correct next posture is observation and one adopted report action, not more
automation.
