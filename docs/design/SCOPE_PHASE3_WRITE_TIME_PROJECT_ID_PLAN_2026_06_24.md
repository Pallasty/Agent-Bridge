# Scope Phase 3 Write-Time Project Id Plan

Date: 2026-06-24
Status: Draft plan, docs-only
Thread: forum #120 posts #4121, #4125, #4126, #4127, #4128

## Summary

Phase 2 read-time scope canonicalization is merged and deployed. It makes
legacy `project:/.../agent-bridge` path scopes compatible at read time, but it
does not change how new memories are written. Phase 3 should decide when a new
project-scoped memory can be written as `project-id:<identity>` instead of a
raw `project:/absolute/path`.

The next safe step is not a production write change. It is a dry-run and trace
plan that proves high-confidence project identity evidence exists, shows which
future writes would change, and defines the tests that prevent same-basename
unrelated repositories from collapsing into one project.

## Current Baseline

Already landed:

- `crates/bridge/src/project_identity.rs` defines canonical project identity
  primitives, alias registry helpers, and evidence levels.
- `crates/bridge/src/mcp_tools.rs` uses read-time compatibility for memory
  search relation and related preview surfaces.
- `crates/bridge/examples/scope_bootstrap_alias_report.rs` reports the
  bootstrap/list alias gap without changing runtime behavior.
- `docs/design/SCOPE_CANONICALIZATION_STABLE_PROJECT_ID_2026_06_24.md`
  establishes the phase model and rejects coarse hard scope prefiltering.
- `docs/design/SCOPE_BOOTSTRAP_ALIAS_VALIDATION_2026_06_24.md` shows that
  startup/list scope omissions are real but too risky to fix with raw SQL
  basename broadening.

Phase 2 boundary:

- no DB migration;
- no write-time scope change;
- no MCP registration;
- no hard scope prefilter;
- no bootstrap/list SQL broadening.

## Problem

New memories are still usually written with caller-provided
`project:/absolute/path` scopes. That preserves the same fragmentation that
Phase 2 only compensates for at read time:

- Mac and aio2 checkouts become different project scopes.
- Worktree suffixes become false cross-project scopes.
- Case differences create separate scopes.
- Parent-directory scopes can strand a memory outside the intended project.

If Phase 3 switches writes too aggressively, it creates the opposite risk:
unrelated repositories with the same basename could collapse into one project,
or low-confidence path fallbacks could look more authoritative than they are.

## Decision

Phase 3 should be staged as:

1. write-time project identity dry-run;
2. explicit trace output;
3. shadow write comparison;
4. owner review;
5. production write change only for high-confidence identities.

Do not write `project-id:<identity>` when resolver evidence is only
`GitRootName` or `PathFallback`.

## Resolver Evidence Policy

Allowed for production `project-id` writes:

- `Explicit`: `AGENT_BRIDGE_PROJECT_ID` or a future reviewed project id file.
- `GitRemote`: normalized remote identity, such as
  `project-id:git:github.com/pallasting/agent-bridge`.

Not allowed for production `project-id` writes by default:

- `GitRootName`: useful for diagnostics, too weak for stored identity.
- `PathFallback`: legacy only.

During transition, write traces should include both:

- proposed canonical scope;
- current legacy scope.

## Dry-Run Report

Add a report-only path before changing `MemorySaveTool` or any store write path.
It may be a CLI/example first. It should not be an MCP tool by default.

Inputs:

- cwd;
- optional explicit project id;
- optional git remote/root override for tests;
- optional sample memory kind/scope;
- optional DB path only if the report summarizes existing rows.

Required output:

- resolver evidence;
- canonical scope;
- legacy scope;
- whether production write would use canonical scope;
- reason if canonical write is blocked;
- rows by current scope if DB inspection is enabled;
- candidate worktree-suffix rows that would be rescued by future canonical
  writes;
- collision warnings for same basename with different stable identities.

Every row that relies on basename-only inference must be marked
`needs_review`, not `production_eligible`.

## Shadow Write Comparison

Before production, a shadow mode should compare current and proposed scopes for
new writes without mutating the chosen scope.

For each project-scoped write request, emit or log:

```text
current_scope=project:/Users/pallasting/Projects/agent-bridge
proposed_scope=project-id:git:github.com/pallasting/agent-bridge
evidence=git_remote
production_eligible=true
legacy_scope_preserved=project:/Users/pallasting/Projects/agent-bridge
```

For low-confidence cases:

```text
current_scope=project:/tmp/scratch
proposed_scope=project-id:name:scratch
evidence=git_root_name
production_eligible=false
reason=resolver_evidence_not_high_confidence
```

The shadow output must be bounded and should avoid leaking private absolute
paths unless the local report is explicitly operator-facing.

## Production Write Behavior

When enabled and high-confidence evidence exists:

- write `scope=project-id:<identity>`;
- preserve the legacy path as metadata or a tag, for example
  `legacy_scope:project:/abs/path`;
- avoid adding many legacy-scope tags if an auxiliary table becomes available;
- keep `global`, NULL, and `domain:*` behavior unchanged.

When high-confidence evidence does not exist:

- keep current legacy `project:/absolute/path` behavior;
- optionally add a trace reason, not a canonical scope.

## Acceptance Gates

Unit tests:

- SSH and HTTPS remotes normalize to the same stable identity.
- `.git` suffix and case differences normalize.
- same basename with different remote owner or host does not collapse.
- `GitRootName` and `PathFallback` do not become production-eligible writes.
- explicit project id outranks git remote.
- legacy scope metadata is preserved when canonical write is eligible.

Dry-run tests:

- Mac Agent-Bridge cwd resolves to a high-confidence git remote identity.
- aio2 Agent-Bridge cwd resolves to the same identity when remote evidence is
  supplied.
- worktree suffix paths can be traced to the same stable identity when their
  git remote evidence matches.
- parent-directory scope remains blocked unless explicit project id evidence is
  supplied.

Eval gate:

- add a worktree-suffix gold case, such as a true Agent-Bridge memory currently
  stranded under an `agent-bridge-*` worktree scope;
- compare Phase 2 legacy basename compatibility with Phase 3 git-remote
  identity;
- Phase 3 must rescue the worktree-suffix case without reducing hard-tier
  recall;
- same-basename different-remote negative control must remain non-local.

Operational gates:

- `cargo test -p ab-bridge project_identity -- --nocapture`;
- focused memory scope relation tests;
- dry-run report output reviewed in forum #120;
- no default MCP surface growth;
- no DB migration in the same slice as write-time behavior.

## Rollback

If production write-time canonical scopes are enabled later, rollback must be
simple:

- disable canonical writes and return to legacy `project:/absolute/path`;
- continue reading `project-id:<identity>` rows through Phase 2 compatibility;
- keep legacy scope metadata for rows written during the experiment;
- do not rewrite rows back unless a separate audited migration is approved.

## Non-Goals

- No write-time behavior change in this plan.
- No memory DB migration.
- No `session_bootstrap` SQL broadening.
- No new MCP tool by default.
- No hard scope prefilter.
- No automatic alias admission from basename-only matching.

## Recommended Next Slice

Implement a report-only dry-run:

- likely as a CLI/example or existing diagnostic command;
- use `ProjectIdentityInput` and `resolve_project_identity`;
- report current legacy scope, proposed canonical scope, evidence, and
  production eligibility;
- include fixture tests for high-confidence vs low-confidence identities;
- post the dry-run report to #120 before changing any write path.

This keeps Agent-Bridge aligned with the Goal C direction: fewer default tools,
more precise continuity state, and measurable project identity repair before
runtime mutation.
