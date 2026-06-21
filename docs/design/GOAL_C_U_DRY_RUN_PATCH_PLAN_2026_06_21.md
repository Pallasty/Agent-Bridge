# Goal C U Dry-Run Patch Plan

Date: 2026-06-21

Plan: `ab_controlled_rsi_goal_c_20260621`, step G3.

This document is the G3 dry-run patch plan for the Goal C `U` surface. It does
not implement the patch. It defines the smallest future patch that should be
safe to implement after the recall-evaluation dependency is stable.

## Status

Current state:

- G0 controlled recursive self-improvement design is done.
- G1 continuity honest ledger inventory is done.
- G2 report-first `U` surface/runbook is done.
- Thread #120 post #3736 claims the `recall_eval` host/model selection fix for
  the Mac/design-lead lane.
- The current mainline `crates/bridge/examples/recall_eval.rs` still documents
  and checks `para-ml` as the semantic anchor, while the Mac store in #3736 was
  reported as `multilingual-e5-small`.

Therefore this dry-run plan treats `recall_eval` host/model selection as an
external dependency. The Codex-RSI lane should not implement that fix unless the
owner lane releases it.

## Selected Action

Selected G3 candidate:

> Add a minimal standing `U` report generator or runbook path that emits a
> board-reviewable Goal C report from existing surfaces, after recall metrics can
> be trusted.

This is selected instead of an executor because G2 has not yet proved that `U`
reports produce adopted actions. It is also selected instead of a new MCP tool
because Goal C and #120 explicitly prefer surface contraction and report-first
proof.

## Preconditions

The patch must not start until one of these is true:

1. `recall_eval` host/model selection is fixed in mainline and documented; or
2. the future patch explicitly marks recall metrics as unavailable/stale and
   exits without claiming continuity lift.

Additional preconditions:

- #120 has no newer owner decision that changes Goal C direction.
- Local `master` is fast-forwarded to both `origin/master` and `github/master`.
- Worktree is clean before branching.
- LSWR-H1 remains design-only unless a run result is posted.

## Proposed Future Patch Scope

Branch:

`codex/goal-c-u-report-dry-run-v1`

Files expected:

- `docs/design/GOAL_C_U_DRY_RUN_PATCH_PLAN_2026_06_21.md` as the design base.
- `docs/reports/goal-c-u/README.md` documenting the report contract.
- `docs/reports/goal-c-u/YYYY-MM-DD.md` for the first generated or manually
  assembled report.
- Optional script only if it avoids tool-surface growth:
  `scripts/generate-goal-c-u-report.sh`.

The optional script must remain a local report helper:

- no MCP registry change;
- no runtime mutation;
- no memory write;
- no SEPL resource edit;
- no automatic commit/push;
- no network call except through explicitly invoked existing tools or local
  commands.

## Report Contract

Every `U` report must include:

1. Source commit and timestamp.
2. Board window read, especially thread #120.
3. Recall/cold-start metrics with explicit host/model selection.
4. LSWR-H1 state: absent, design-only, run failed, run passed, or stale.
5. L6 falsified/shelved state.
6. BioCortex offline/runtime boundary state.
7. Tool atlas and dispatch audit snapshot.
8. Readiness/lifecycle snapshot.
9. Event-spine chain head.
10. Work-memory context rows used, if any.
11. Proposed actions with owner, external anchor, falsifier, rollback path, and
    next decision.

The report must have a clear top-level verdict:

- `actionable`: at least one proposed action has an external anchor and owner.
- `blocked`: required anchor missing or stale.
- `observe_only`: useful telemetry, but no safe action.
- `stop`: falsifier triggered.

## Dry-Run Checks

Before implementing the future patch, run these checks manually:

```bash
git status --short --branch
git fetch origin
git fetch github
git log --oneline --decorate -5
rg -n "para-ml|multilingual-e5|AGENT_BRIDGE_ONNX_MODEL|confirm_real_embedder" \
  crates/bridge/examples/recall_eval.rs docs/design docs/reports -S
```

If the recall anchor still hard-codes the wrong host/model, the future patch
must produce `blocked` and must not claim `U` continuity lift.

## Verification Plan

Documentation-only verification:

```bash
git diff --check
```

If a helper script is added:

```bash
bash -n scripts/generate-goal-c-u-report.sh
```

If the helper script runs local checks, its first report should include:

- exact command lines used;
- whether recall metrics were measured, skipped, or blocked;
- `tool_atlas_snapshot` summary;
- `mcp_dispatch_audit` summary;
- `readiness_audit` status;
- `mcp_lifecycle_digest` status;
- `event_spine_snapshot` chain head;
- board posts consumed.

No cargo test is required for a docs-only report helper unless Rust code is
changed.

## Rollback

Rollback is simple because the future patch is docs/script-only:

```bash
git revert <future-commit>
```

Do not revert owner-lane `recall_eval` fixes from this lane.

## Falsifiers

Do not implement or keep the future report helper if:

- it cannot distinguish measured recall from skipped semantic recall;
- it duplicates existing `readiness_audit`, `tool_atlas_snapshot`, or
  `mcp_dispatch_audit` without adding a Goal C decision layer;
- it creates a new MCP surface before repeated report use proves value;
- the first report proposes no externally anchored action;
- downstream lanes ignore the report after repeated board-visible attempts.

## G3 Exit Criteria

G3 is complete when this dry-run patch plan is committed and posted to #120. A
future implementation should be a separate G4-or-later decision unless the owner
explicitly asks this lane to implement the report helper next.

The next plan step, G4, should decide whether a dedicated approval-gated executor
is justified. Based on current evidence, the expected G4 recommendation is
likely "no executor yet; collect at least one adopted `U` report action first."
