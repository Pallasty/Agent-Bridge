# Agent-Bridge working instructions

Read `CLAUDE.md` for project layout, build, deployment, and secret-handling
rules. Read `docs/ACTIVE-PRODUCT-ROADMAP.md` before opening a product lane.

Do not trigger CI. Synchronize code over SSH, include `[skip ci]` in sync
commits, and use `-o ci.skip` for GitLab pushes. Do not dispatch workflows.

## R7 collection during ordinary work

When resuming genuinely interrupted work, encountering a real task failure,
or checking an already explicit due commitment, follow
`docs/operations/R7_ASSISTED_SHADOW_COLLECTION.md`. The working agent owns
identification, preview, and eligible record submission; do not require the
owner to notice the event or type the command. This is a foreground workflow,
not an automatic event source, background monitor, or wake authorization.
