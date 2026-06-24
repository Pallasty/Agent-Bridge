# Scope Bootstrap Alias Validation

Date: 2026-06-24
Status: Validation note, docs-only
Thread: forum #120 posts #4116, #4117

## Summary

The read-time project-scope canonicalization slice fixes in-memory scope relation checks for memory search and related-key previews. It does not fix `session_bootstrap` or the store-level `list_memories_in_scope` SQL path.

That remaining gap is real: the current startup/list path misses high-value same-project Agent-Bridge memories created on aio2 or in isolated worktrees. However, directly broadening the SQL predicate by basename would affect the startup surface too aggressively. The next runtime slice should be designed around an explicit alias set or resolver evidence, not raw SQL basename matching.

## Current Measurement

Read-only SQL was run against the local Mac store:

- DB: `~/Library/Application Support/agent-bridge/state.db`
- Current cwd under test: `/Users/pallasting/Projects/agent-bridge`
- Current SQL behavior under test: `SqliteStore::list_memories_in_scope`

Results:

| Metric | Rows |
|---|---:|
| active memories | 3087 |
| current SQL-visible rows for Mac Agent-Bridge cwd | 2198 |
| current SQL local, non-global rows | 150 |
| agent-bridge-named project rows | 411 |
| agent-bridge-named rows omitted by current SQL | 261 |

Omitted rows by kind:

| Kind | Omitted Rows | Avg Importance |
|---|---:|---:|
| decision | 158 | 0.889 |
| session_handoff | 28 | 0.596 |
| lesson | 25 | 0.758 |
| fact | 14 | 0.622 |
| work_memory | 12 | 0.625 |
| context | 8 | 0.663 |
| observation | 6 | 0.451 |
| todo | 6 | 0.640 |
| evidence | 2 | 0.525 |
| finding | 1 | 0.500 |
| implementation | 1 | 0.500 |

The high-importance omissions are mostly under aio2 paths such as:

- `project:/Data/CascadeProjects/agent-bridge`
- `project:/Data/CascadeProjects/Agent-Bridge`
- `project:/Data/CascadeProjects/agent-bridge-*` worktree scopes

This means startup continuity can miss important same-project decisions, lessons, and handoffs.

## Why Direct SQL Broadening Is Risky

The current SQL predicate is intentionally simple:

```sql
scope IS NULL
OR scope = 'global'
OR scope = ?ctx
OR (scope LIKE 'project:%' AND ?ctx LIKE (SUBSTR(scope, 9) || '%'))
```

Adding basename matching directly to this predicate would:

- affect every `session_bootstrap` block that uses scoped list queries;
- apply before rank, budget, and block-specific curation;
- risk pulling unrelated repos with the same basename;
- make parent-directory and worktree suffix behavior hard to audit;
- make the first startup surface after deploy broader than the already-reviewed memory search relation change.

The startup surface is higher risk than interactive memory search because it is injected automatically.

## Safer Runtime Design Options

### Option A: Explicit Alias Set

Build a reviewed alias set for the requested cwd, then pass those aliases to the store query.

Example alias set:

```text
project:/Users/pallasting/Projects/agent-bridge
project:/Data/CascadeProjects/agent-bridge
project:/Data/CascadeProjects/Agent-Bridge
```

Pros:

- auditable;
- no same-basename surprise;
- can be logged and dry-run before use.

Cons:

- needs a source of alias truth;
- requires a migration or sync process to keep aliases fresh across nodes.

### Option B: Resolver-Evidence Alias Set

Resolve the current cwd to a stable project identity, then include only rows whose legacy scope can be proven to share that identity.

Acceptable proof:

- explicit `.agent-bridge/project-id`;
- stored `project-id:<identity>` scope;
- stored metadata linking legacy path scope to a stable id;
- reviewed dry-run migration output.

Rejected proof:

- basename-only equality as the only signal for startup injection.

Pros:

- matches the stable project identity design;
- safe path toward write-time canonical scopes.

Cons:

- legacy rows currently do not carry enough metadata, so this needs a report/migration precursor.

### Option C: Two-Stage Bootstrap Supplement

Keep `list_memories_in_scope` unchanged, but add a bounded bridge-level supplement:

1. Fetch the current scoped rows as today.
2. Fetch a small, separately budgeted candidate pool.
3. Filter candidates with the same read-time compatibility helper used by memory search.
4. Emit supplement rows under a distinct heading such as `Same-project aliases`.
5. Include trace metadata showing why each alias was admitted.

Pros:

- does not mutate store SQL;
- can be block-budgeted and disabled independently;
- easier to evaluate in Codex/Claude bootstrap output.

Cons:

- can still admit basename-only rows unless gated;
- may require overfetching to avoid missing important rows.

## Recommended Next Runtime Slice

Do not change store SQL yet.

Implement a dry-run report first:

1. Input: cwd and optional kind.
2. Output current SQL-visible counts.
3. Output omitted same-project candidates by scope, kind, importance, and key preview.
4. Output candidate admission reason:
   - exact path;
   - path ancestor;
   - stable project id;
   - explicit alias;
   - basename fallback.
5. Mark basename-only rows as `needs_review`, not auto-admitted.

Only after that report is reviewed should runtime bootstrap add an alias supplement.

## Acceptance Gates

Any runtime bootstrap/list alias implementation must pass:

- global/NULL rows remain unchanged;
- exact current-cwd rows remain unchanged;
- aio2 `project:/Data/CascadeProjects/agent-bridge` same-project rows can be surfaced with trace evidence;
- parent scope `project:/Data/CascadeProjects` is not admitted by basename or prefix alone;
- same basename but different stable remote owner or host is not admitted;
- worktree suffix scopes are admitted only when resolver or alias evidence proves they belong to the same project;
- `session_bootstrap` output labels alias rows distinctly until write-time canonical scopes exist;
- a dry-run report shows before/after counts before any production behavior is enabled.

## Non-Goals

- No DB migration in this slice.
- No write-time scope change.
- No new MCP tool by default.
- No direct SQL basename broadening.
- No claim that phase12 fully fixes startup continuity.

## Decision

The omission problem is large enough to justify follow-up work, but the next safe step is a dry-run alias report or explicitly traced bootstrap supplement. Treat direct SQL basename broadening as rejected unless a future owner explicitly accepts the startup-surface risk.
