# Semantic Rebalance Branch Closure Audit - 2026-07-01

## Status

`origin/claude/semantic-rebalance-20260630` is no longer an unmerged
follow-up branch from the local fetched remote-ref view.

The branch tip:

- `06df013 feat(store): rebalance semantic retrieval ranking weights (owner-signed-off)`

is contained by current `origin/master` through:

- `ef5d05e merge: rebalance semantic retrieval ranking`

Current `HEAD`, `origin/master`, and `origin/HEAD` are:

- `ed7f0cc docs(memory): record correction cosurface link review`

## Evidence

Commands run from `/Data/CascadeProjects/agent-bridge` after
`git fetch --prune origin`:

```text
git log --oneline --decorate --left-right --cherry-pick origin/master...origin/claude/semantic-rebalance-20260630
```

Result: only left-side (`origin/master`) commits were listed; no right-side
commits remain unique to `origin/claude/semantic-rebalance-20260630`.

```text
git diff --stat origin/master...origin/claude/semantic-rebalance-20260630
git diff --name-status origin/master...origin/claude/semantic-rebalance-20260630
```

Result: no diff output.

```text
git merge-tree origin/master origin/claude/semantic-rebalance-20260630
```

Result: clean tree output only:

```text
51b9b423e83abd40ed08b517b2d466b8ed30a769
```

`git branch -r --contains origin/claude/semantic-rebalance-20260630`
included `origin/master`, confirming the branch tip is reachable from master.

## Implementation Shape Now On Master

The landed code changes are in `crates/store/src/sqlite.rs`:

- semantic ranking weights are centralized in `semantic_rank_weights()`;
- the owner-signed-off default is cosine-led, with importance, memory, and
  feedback as near-tie breakers;
- runtime rollback/A-B handles exist:
  - `AGENT_BRIDGE_SEMANTIC_RANK_LEGACY=1`
  - `AGENT_BRIDGE_SEMANTIC_W_COS`
  - `AGENT_BRIDGE_SEMANTIC_W_IMP`
  - `AGENT_BRIDGE_SEMANTIC_W_MEM`
  - `AGENT_BRIDGE_SEMANTIC_W_FB`

This is separate from the correction co-surface work. The correction review
remains correct that the two levers should not be mixed, but the semantic
rebalance branch itself should no longer be treated as pending rebase or pending
merge.

## Verification

Effective checks:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store semantic_rank_weights_resolve -- --nocapture
```

Passed: 1/1.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-bridge --no-default-features memory_search_semantic_cosine_bounded_and_below_blended_score -- --nocapture
```

Passed: 1/1.

Non-effective check, recorded to avoid overstating evidence:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store memory_search_semantic -- --nocapture
```

This completed successfully but matched 0 tests, so it is not counted as
behavioral evidence.

## Queue Decision

Remove "PR #32 semantic rebalance needs rebase/review/owner merge" from the
active follow-up queue.

Remaining meaningful items are still gated or operational-window constrained:

- correction co-surface enablement / live backfill: owner-gated;
- bounded coactivation latch: owner-gated implementation work;
- SQLite `VACUUM`: maintenance-window work;
- any production retrieval-order or ranking-policy change beyond the already
  landed semantic rebalance: owner-gated.

Safe non-gated next slices should stay read-only or documentation-only, such as
measurement packets, branch/queue audits, or review-plan assembly.
