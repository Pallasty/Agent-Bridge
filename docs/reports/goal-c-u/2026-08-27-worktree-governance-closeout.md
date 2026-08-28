# Worktree governance closeout — 2026-08-27

## Outcome

The cleanup campaign is closed after two admitted batches removed ten worktrees
and released approximately 76.03 GiB. The durable registered population fell
from 82 to 72. The closeout report itself is authored in one additional
isolated worktree, so a live inventory taken while this branch exists reports
73 registrations.

Both remote baselines were freshly fetched and matched at
`e6ccdcc4a5af053fd53d3502257413ed650c78b4` when this closeout started. The
host had approximately 2.55 TiB free after cleanup. Capacity pressure therefore
does not justify continuing destructive cleanup.

## Standing decision

- Pause bulk worktree deletion.
- Treat dirty worktrees as owner-custody HOLD. Never clean, reset, stash, or
  remove them as part of worktree governance.
- Treat a head not contained by both freshly fetched remote `master` refs as
  integration-review HOLD. Containment may later be replaced only by explicit
  patch-equivalence evidence.
- Treat detached heads without a verified branch or
  `refs/archive/worktree/...` recovery point as recovery-ref HOLD.
- A future cleanup campaign must refetch both remotes, re-run status,
  containment, ref, lock, cwd, and process-argument checks, then obtain a new
  exact deletion authorization.

The HOLD sets below overlap. In particular, the primary checkout is both dirty
and not contained by the current remote baseline. Counts must not be added as
if they were disjoint.

## Dirty owner-custody HOLD (4)

| Entries | HEAD | Branch | Path |
|---:|---|---|---|
| 31 | `32a748c97a5914ac13b023e9ac71f04403cf99c6` | `master` | `/Users/pallasting/Projects/agent-bridge` |
| 2 | `f0ac1b8adab66f43929519034d0f5ffec7d621ca` | `codex/capabilities-compact-mobile-20260724` | `/Users/pallasting/Projects/agent-bridge-capabilities-compact-mobile-20260724` |
| 1 | `0d1ab06bf3a357eb8e3527b39d6d466939b331b9` | `codex/free-recall-strategy-r1` | `/Users/pallasting/Projects/agent-bridge-free-recall-strategies` |
| 7 | `ddc3471a278cd024612fa61f2c6eef9e2f19d258` | `codex/g14-wasi-g2g-host-build-remediated-20260719` | `/Users/pallasting/Projects/agent-bridge-g14-wasi-g2g-host-build-remediated` |

## Integration-review HOLD (50)

Fifty registered heads were not ancestors of both freshly fetched remote
`master` refs. They remain intact. This cohort includes the primary checkout,
the macOS semantic/AX chain, S14/S15 supervisor chain, AG-UI convergence,
publisher hardening predecessor, explicit-trajectory chain, compressive-memory
custody chain, mobile-text predecessor, and older VP5/R3 containment work.

This is intentionally a live-derived cohort rather than a deletion list. Its
exact members must be regenerated before any later decision because remote
movement, merges, and patch-equivalence review can change membership.

## Recovery-ref HOLD (1)

`/Users/pallasting/Projects/.worktrees/agent-bridge-deploy-qualification-b6e1b822-20260824`
is clean and contained, but its detached head
`b6e1b822be0d84d9354b2d4e8c263ab7b7cf8be2` had no branch or archive recovery
ref during the closeout scan. It remains untouched.

## Deferred clean cohort

After the second removal batch, 18 clean, contained, recoverable worktrees
remain outside the HOLD sets. They are deferred rather than admitted for more
cleanup because space pressure is resolved. Reversibility alone is not a reason
to keep deleting useful local build surfaces.

## Reproduction

Use the repository-owned truth snapshot as the first pass:

```bash
python3 scripts/agent-bridge-project-truth-snapshot.py \
  --repo /Users/pallasting/Projects/agent-bridge \
  --probe-remotes \
  --inspect-worktrees \
  --include-clean-worktrees
```

Then independently check each proposed target for containment against both
fresh remote refs, branch/archive recovery, lock state, process cwd, and process
arguments. The snapshot is inventory evidence; it is not deletion authority.

## Next product gate

Return to Agent-Bridge capability work. Do not reopen worktree cleanup unless
capacity pressure returns, a branch owner requests reconciliation, or a bounded
candidate has a concrete operational cost.
