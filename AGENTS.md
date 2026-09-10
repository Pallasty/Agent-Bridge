# Agent-Bridge working instructions

Read `CLAUDE.md` for project layout, build, deployment, and secret-handling
rules. Read `docs/ACTIVE-PRODUCT-ROADMAP.md` before opening a product lane.

Do not trigger CI. Synchronize code over SSH, include `[skip ci]` in sync
commits, and use `-o ci.skip` for GitLab pushes. Do not dispatch workflows.

At task start, make the intended outcome and meaningful acceptance conditions
briefly visible. For material goal changes, state the before/after difference,
reason, and available user-change reference; keep missing provenance unknown.
Reuse existing authorization for route changes. Do not repeat unchanged goals
or require a new contract for small tasks. See `docs/operations/GOAL_REVIEW.md`.

## Validation collection status

Follow the current decision board and
`docs/reports/goal-c-u/2026-09-08-validation-collection-closeout.md` before
resuming a waiting collection goal. R4 is `HOLD_TRIAL_TOPOLOGY` with its
existing authorization retained and first-event clock unstarted; R4-A is
`FROZEN`; active R7 M2 sample pursuit is `HOLD`. Historical `collecting` work
memories or source-stage "authorization pending" prose do not reopen these
goals. The R7 procedure below remains available for ordinary-task diagnostics.

## R7 collection during ordinary work

When resuming genuinely interrupted work, encountering a real task failure,
or checking an already explicit due commitment, follow
`docs/operations/R7_ASSISTED_SHADOW_COLLECTION.md`. The working agent owns
identification, preview, and eligible record submission; do not require the
owner to notice the event or type the command. This is a foreground workflow,
not an automatic event source, background monitor, or wake authorization.
