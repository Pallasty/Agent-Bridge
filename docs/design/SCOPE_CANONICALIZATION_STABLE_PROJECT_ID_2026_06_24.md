# Scope Canonicalization With Stable Project Identity

Date: 2026-06-24
Status: Draft RFC, docs-only
Thread: forum #120 posts #4098, #4103, #4106, #4107

## Summary

Agent-Bridge currently treats `project:/absolute/cwd` as the project identity for memory scope. That was simple and local, but it breaks down across machines, case differences, and isolated worktrees. The same logical project can become many mutually cross-scope projects, so `local_only` and soft scope penalties can hide or demote memories that should be local.

The next production direction should not be coarse hard prefiltering. The measured root cause is scope identity fragmentation. The fix should introduce a stable project identity and a controlled compatibility layer for legacy path scopes before any runtime ranking change.

## Current Evidence

From the 2026-06-24 local store:

| Bucket | Rows | Distinct Scopes |
|---|---:|---:|
| global/null | 2046 | 2 |
| agent-bridge-named project scopes | 411 | 15 |
| other scoped rows | 628 | 20 |

Examples of split scopes for the same logical Agent-Bridge project:

- `project:/Data/CascadeProjects/agent-bridge`
- `project:/Users/pallasting/Projects/agent-bridge`
- `project:/Data/CascadeProjects/Agent-Bridge`
- `project:/Data/CascadeProjects/agent-bridge-palace-apply-audit`
- `project:/Data/CascadeProjects/agent-bridge-*` isolated worktrees

The current code confirms the mechanism:

- `MemorySaveTool` accepts caller-provided `scope` verbatim and documents `project:/abs/path`.
- `session_bootstrap` and scoped list paths pass the caller `cwd` to `list_memories_in_scope`.
- `SqliteStore::list_memories_in_scope` only matches exact `scope`, `global`/NULL, or path-prefix overlap.
- `memory_search_scope_relation` in `mcp_tools.rs` mirrors the same absolute-path relation and applies `local_only`, `local_plus_global`, or `exploratory` behavior after retrieval.

Related measurements:

- #4098 falsified coarse hard scope filtering: hard filtering did not improve the real retrieval objective and exposed fragmentation.
- #4103 independently measured that coarse project-scope hard filtering raised non-cross purity but sharply dropped recall on the current Mac snapshot. The exact numbers differ because the harnesses define purity differently, but the decision agrees: do not productionize coarse hard filtering.
- #4106 reports that a canonical-scope arm using basename plus lowercase recovered same-project false cross-scope cases and beat the current production soft relation on that harness. Treat this as strong evidence for canonicalization, not as proof that basename alone is a safe production identity.
- #4098 also reports GTE-era whitening remains secondary: it reduces anisotropy but does not improve hard-tier R@10.

## Problem

Absolute cwd is not a stable project identity.

It changes when:

- the same repo is checked out on Mac vs aio2;
- the same repo is cloned under a different root;
- a worktree appends a suffix to the path;
- path case changes, such as `agent-bridge` vs `Agent-Bridge`;
- an agent runs from a parent or nested directory.

The resulting failure mode is not just "cross-project pollution". It is also false cross-project separation: same-project memories are treated as cross-scope and get hidden or demoted.

## Non-Goals

- Do not make hard scope prefilter the default.
- Do not rewrite all memory rows without a dry-run and rollback story.
- Do not erase legitimate cross-domain analogy. Exploratory retrieval remains valuable.
- Do not require a Git remote for non-git or throwaway projects.
- Do not expose private absolute paths in new canonical public identifiers unless explicitly approved.

## Proposed Scope Model

Introduce a stable project identity layer that can be derived from cwd but is not the cwd itself.

### Canonical Project Id

Preferred derivation order:

1. Explicit override: `AGENT_BRIDGE_PROJECT_ID` or future `.agent-bridge/project-id`.
2. Git remote identity: normalized remote host plus owner plus repo slug, for example `git:github.com/pallasting/agent-bridge`.
3. Git repository root slug: normalized root basename, for example `name:agent-bridge`, as a lower-confidence fallback.
4. Legacy fallback: `path:/absolute/cwd`, used only when no stronger identity exists.

Normalization rules:

- trim whitespace;
- lowercase host, owner, and repo slug;
- strip `.git`;
- normalize common SSH/HTTPS remote forms to the same identity;
- do not follow symlinks blindly without recording the resolved path used.

### Stored Scope Forms

Keep the existing `scope` column, but define versioned forms:

- `global` or NULL: global memories.
- `domain:<name>`: technology or domain grouping, unchanged.
- `project:/abs/path`: legacy path scope, still readable.
- `project-id:<identity>`: canonical project scope, new target form.

The exact prefix is intentionally distinct from `project:` so code can avoid treating a stable id as a path.

## Compatibility Strategy

The safest rollout is read-time compatibility first, write-time migration later.

### Phase 1: Pure Resolver

Add a pure `ProjectIdentity` resolver:

```text
cwd -> {
  canonical_scope: project-id:git:github.com/pallasting/agent-bridge,
  legacy_scope: project:/Users/pallasting/Projects/agent-bridge,
  evidence: explicit | git_remote | git_root_name | path_fallback
}
```

This phase should include unit tests only. It should not change memory writes or reads.

### Phase 2: Read-Time Alias Matching

Teach scope relation checks to compare canonical identities before falling back to legacy path overlap.

Required behavior:

- `project:/Users/pallasting/Projects/agent-bridge` and `project:/Data/CascadeProjects/agent-bridge` should be local when their derived canonical id matches.
- `project:/Data/CascadeProjects/agent-bridge-feature-x` should be local only when the resolver can prove it is a worktree of the same repo or an approved alias.
- `project:/Data/CascadeProjects` should not become local merely because it is a parent directory.
- `global`/NULL behavior remains unchanged.

This phase can be deployed without rewriting rows.

### Phase 3: Write-Time Canonical Scope

New project-scoped memory writes should use `project-id:<identity>` when the resolver confidence is high.

For backward compatibility, preserve the old path as metadata:

- tag: `legacy_scope:project:/abs/path`, or
- future auxiliary table if tags are too noisy.

Do not switch writes when the resolver falls back to path-only identity.

### Phase 4: Migration Dry-Run

Add a read-only report before any DB mutation:

- count rows by current scope;
- proposed canonical scope;
- resolver evidence;
- confidence;
- collisions;
- rows that would remain legacy path-scoped;
- affected `session_handoff`, `decision`, `lesson`, and `work_memory` rows separately.

Only after review should a write-capable migration exist.

### Phase 5: Controlled Rewrite

If approved, rewrite eligible legacy scopes to `project-id:<identity>` with:

- SQLite backup path printed before mutation;
- per-row before/after audit JSONL;
- idempotent dry-run hash;
- rollback instructions;
- no mutation of `global`, NULL, `domain:*`, `outcome:*`, or `work_memory_*` scopes unless explicitly included.

## Acceptance Gates

### Unit Tests

- SSH and HTTPS remotes normalize to the same id.
- `.git` suffix is stripped.
- case differences normalize.
- Mac and aio2 Agent-Bridge paths map to the same id when remote evidence matches.
- sibling projects with the same basename but different remote owner/host do not collapse.
- basename-only fallback is visibly marked lower confidence and cannot override higher-confidence remote evidence.
- parent directory scopes do not become local by basename alone.

### Eval Gates

- Add or reuse an explicit scope experiment mode that is not part of default `recall_eval` output.
- Include arms for legacy path relation, canonical relation, and current production relation.
- Track local-gold, global-only, and cross-scope-gold separately.
- Production eligibility requires:
  - same-project cross-node/worktree gold cases improve or stay visible;
  - hard-tier R@10 does not drop against current raw/production semantic baseline;
  - legitimate cross-domain gold cases remain visible in exploratory mode;
  - no increase in false local matches for unrelated repos with the same basename.

### Live Surface Gates

- `session_bootstrap(cwd=/Users/pallasting/Projects/agent-bridge)` can surface an aio2-created Agent-Bridge project memory after read-time aliasing.
- `memory_search(... scope=Mac agent-bridge scope, scope_mode=local_only)` can retrieve same-repo aio2/worktree rows after aliasing.
- `scope_mode=exploratory` still includes cross-project analogy rows, but they are not mislabeled local.
- `memory_graph_topology` scoped views do not accidentally absorb parent-directory or sibling-project memories.

## Recommended Next Step

Do Phase 1 and Phase 2 together as a narrow implementation slice:

1. Add a pure resolver module with tests.
2. Add read-time canonical relation matching behind a conservative feature gate or internal helper.
3. Add an explicit eval mode to measure legacy vs canonical relation.
4. Do not change write-time scopes or migrate rows yet.

The production question is not "should scope be hard-filtered?" The measured question is now "can Agent-Bridge correctly know what the same project is across hosts and worktrees?"
