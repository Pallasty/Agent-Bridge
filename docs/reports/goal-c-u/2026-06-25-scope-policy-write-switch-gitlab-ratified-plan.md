# Scope Policy Write Switch GitLab-Ratified Plan

Date: 2026-06-25
Status: design and gate plan only
Thread: forum #120 posts #4297 and #4312

## Summary

Owner ratified the Agent-Bridge canonical host as GitLab in #120 post #4297:

```text
canonical_project_id=project-id:git:gitlab.com/pallasting/agent-bridge
production_project_id_writes_authorized=false
```

This closes the previous host-choice ambiguity but does not authorize production
`project-id:*` writes, memory row migration, backfill, graph writes, or MCP
surface growth. The next safe step is a no-op shadow comparison and reviewed
implementation gate that proves write requests would canonicalize only approved
Agent-Bridge scopes and would block or preserve every ambiguous case.

## Preflight State

At the start of this plan, GitHub `master` was ahead of GitLab `origin/master`
by five GTE review/probe commits. The local checkout was fast-forwarded to
GitHub and then pushed to GitLab so both forges agreed at:

```text
33d55e0e5e0ee61fd7d248f0be8aea55a1d2ddd7
```

This keeps the newly ratified GitLab-primary contract coherent before any
write-policy design.

Merge audit refresh on 2026-06-25 observed `origin/master` and `github/master`
both at `9e0d8cf0729d022520d3a222bbbbe70f5a1c082b`. The later target commits
do not touch this plan's four scope-policy document files, and a merge-tree
preflight reported no text conflicts.

## Current Gate Evidence

All commands below are report-only and perform no store writes.

| Gate | Result | Key evidence |
|---|---:|---|
| `scope_canon_rescue_gate` | PASS | live Mac store: basename local rows `386`, registry local rows `449`, rescued worktree-suffix rows `63`; same-basename diff-remote and parent-dir controls stayed non-local |
| `scope_policy_admission_gate` with main checkout cwd | PASS | root and child admitted; unregistered sibling and parent need review; non-project and different project-id blocked |
| `scope_write_identity_dry_run` with main checkout cwd | eligible trace | GitLab remote evidence produced `project-id:git:gitlab.com/pallasting/agent-bridge`, high confidence, production eligible only behind a later explicit gate |
| `scope_write_shadow_comparison` with main checkout cwd | PASS | root/child/known suffix canonicalize in shadow; unregistered sibling and parent stay legacy-needs-review; GitHub project-id is blocked as alternate forge |
| `scope_write_shadow_comparison` in this isolated worktree | FAIL as expected | the temporary worktree is not in the reviewed alias registry, so it must not canonicalize by basename alone |

The isolated-worktree failure is a useful negative control, not a blocker. It
proves the default policy does not silently bless arbitrary `agent-bridge-*`
worktrees.

## Reviewed Initial Alias Registry

Use this as the first GitLab-ratified alias policy for no-op shadow comparison:

```text
project-id:git:gitlab.com/pallasting/agent-bridge=
project:/Data/CascadeProjects/agent-bridge,
project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge,
project:/Users/pallasting/Projects/agent-bridge,
project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate,
project:/Data/CascadeProjects/agent-bridge.wt-tts,
project:/Data/CascadeProjects/agent-bridge-lcc0
```

Do not auto-admit additional worktree suffixes by basename. New suffixes must go
through `scope_policy_admission_gate` and owner-visible review before joining
the registry.

## Implementation Plan

### Gate 1: No-Op Shadow Comparison

Add or run a bounded shadow comparison path that records, for project-scoped
memory save requests:

- current requested scope;
- proposed GitLab canonical scope;
- identity source: `scope`, `policy`, `env`, or `git_remote`;
- whether the request is in the reviewed alias registry;
- shadow action: `canonicalize_in_shadow`, `keep_legacy_needs_review`,
  `keep_unchanged`, or `blocked`;
- legacy scope that would be preserved if a later production experiment writes
  canonical scope.

This gate must not change the stored scope used by `MemorySaveTool`.

### Gate 2: Owner Decision Packet For Production Experiment

Only after shadow comparison evidence is reviewed, prepare a separate owner
packet with:

- exact alias registry hash or literal registry;
- expected count of requests by shadow action;
- negative controls: same basename different remote, unregistered worktree
  suffix, parent directory, non-project scope, GitHub alternate forge
  `project-id`, and unrelated project-id;
- rollback switch;
- statement that DB migration/backfill remains false.

### Gate 3: Production Write Experiment

If and only if the owner explicitly approves a production experiment:

- canonicalize only admitted project scopes;
- preserve legacy scope metadata or tag for every canonicalized write;
- keep `global`, NULL, `domain:*`, and unreviewed project scopes unchanged;
- emit a compact trace for the first N writes;
- keep Phase 2 read-time compatibility enabled so rollback can simply stop new
  canonical writes.

### Gate 4: Migration/Backfill

Historical row migration is a separate Phase 5-style decision. It is not part of
this plan and remains unauthorized.

## Required Acceptance Tests

Before any production experiment:

- `cargo test -p ab-bridge project_identity -- --nocapture`
- `cargo test -p ab-bridge scope_policy -- --nocapture` or the closest focused
  scope-policy tests available at that point
- `cargo run -p ab-bridge --example scope_canon_rescue_gate`
- `AB_SCOPE_POLICY_ADMISSION_CWD=/Users/pallasting/Projects/agent-bridge cargo run -p ab-bridge --example scope_policy_admission_gate`
- `AB_SCOPE_SHADOW_CWD=/Users/pallasting/Projects/agent-bridge cargo run -p ab-bridge --example scope_write_shadow_comparison`
- one negative-control run from a non-registered worktree, expected to fail or
  produce only `keep_legacy_needs_review`
- `git diff --check`

## Non-Authorizations

This plan does not authorize:

- production `project-id:*` writes;
- DB migration or backfill;
- rewriting existing `project:/...` rows;
- memory search ranking/order changes;
- graph writes;
- session bootstrap SQL broadening;
- MCP tool/profile expansion;
- automatic alias admission from basename-only matching;
- treating GitHub as equivalent to GitLab without explicit owner supersession.

## Rollback

While this remains report-only, rollback is simply to keep writing legacy
`project:/absolute/path` scopes. If a later production experiment is approved,
rollback must disable canonical writes while preserving read-time compatibility
for rows already written as `project-id:git:gitlab.com/pallasting/agent-bridge`.
