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

## CLI governance maintenance

Start with `docs/design/CLI-GOVERNANCE-STATUS.md` for current completion,
verification routes and restart conditions. Sequential extraction and the
finite G1–G7 work are closed; continue only from a demonstrated maintenance
trigger or explicitly changed scope. Do not generate a new stage merely to
satisfy a generic continuation request.

S0–S21 sequential extraction is closed. Follow
`docs/design/CLI-GOVERNANCE-MAINTENANCE-GOALS-2026-09-14.md` for the finite
maintenance contract and existing S5-V/S17 retention decisions. Do not invent
another extraction stage solely because main.rs is large.

S18–S21 report/source bindings and selected behavior probes are enforced by
`scripts/eval/cli_governance_evidence.py` in pre-commit, including module-only
changes. Update and stage the matching evidence when bound files change;
execution requires the tracked worktree and index to agree. Keep actual
behavior evidence separate from historical report digest validation.

Fresh isolated CLI comparisons are also required for selected profiles under
`docs/design/CLI-GOVERNANCE-LIVE-PARITY-GOAL-2026-09-14.md`. The runner builds
a pinned archive baseline and the staged candidate; allow both builds to finish
without modifying the index or source. Reports and build logs remain under
`CARGO_TARGET_DIR/governance-live/run-*`.

For portable, read-only CLI evidence review, follow
`docs/design/CLI-GOVERNANCE-PORTABLE-EVIDENCE-GOAL-2026-09-14.md`. Always select
the tested implementation commit independently; the later evidence-only commit
has a different tree. Offline verification does not replace fresh pre-commit runs.

Fresh regression execution also requires no tracked `assume-unchanged` or
`skip-worktree` flags; see
`docs/design/CLI-GOVERNANCE-INDEX-CUSTODY-GOAL-2026-09-14.md`. Use a complete
checkout for execution. The gate reports these flags without clearing them.
