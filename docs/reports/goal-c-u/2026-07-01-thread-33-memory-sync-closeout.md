# Thread 33 Memory-Sync Closeout

Date: 2026-07-01

Status: `APPLIED_NARROW_RESOLVE_PASS / REVERSIBLE / HARDWARE_WET_TEST_DEFERRED`

## Summary

Thread `#33` is now resolved as a completed Agent-Bridge memory-sync
version-vector hardening lane.

Applied status change:

| Thread | Closeout post | Old status | New status | Reason |
|---:|---:|---|---|---|
| `#33` Memory-Sync Hardening / version-vector conflict detection | `#2835` | `open` | `resolved` | The thread records design, implementation, e2e logic validation, wrapper/node-id activation, runbook publication, Mac readiness, and an owner closeout decision that defers true hardware wet-test as non-blocking. |

## Evidence Read

Full-thread read of `#33` showed:

- `#1719`: Syncthing-inspired memory-sync hardening design landed. The key
  shift was from git-branch conflict handling to per-record version-vector
  merge.
- `#1720` to `#1723`: `VersionVector`, schema migration, sync envelope carry,
  and `VersionVectorMerge` import behavior landed. Concurrent same-key edits
  preserve both versions through conflict copies instead of silent LWW loss.
- `#1724` to `#1726`: single-machine e2e validation, wrapper
  `AB_SYNC_NODE` activation, sync `conflict_copies` visibility, and the
  two-node wet-test runbook landed.
- `#1727`: Mac-side readiness was recorded for a coordinated wet-test.
- `#1728`: owner closeout decision marked the lane logic-validated and deferred
  true hardware cross-network wet-test as non-blocking. The runbook remains
  ready if a later interactive aio2/Mac window opens.

Fresh source readback in this pass confirmed current tree still contains:

```text
crates/store/src/version_vector.rs
ImportConflictPolicy::VersionVectorMerge
memory import conflict_copies reporting
scripts/wrapper/agent-bridge-wrapper.sh AB_SYNC_NODE injection
docs/design/MEMORY_SYNC_VERSION_VECTOR_BORROW_2026_05_24.md
docs/design/MS_TWO_NODE_WET_TEST_RUNBOOK_2026_05_24.md
```

Focused verification:

```text
cargo test -p ab-store vv_merge_e2e --lib -- --nocapture
```

Result:

```text
test sqlite::tests::vv_merge_e2e_disjoint_keys_both_survive ... ok
test sqlite::tests::vv_merge_e2e_concurrent_same_key_preserves_both ... ok

test result: ok. 2 passed; 0 failed
```

The existing mixed-script warning for the Greek beta coactivation test name was
observed and is unrelated to this docs/status pass.

## Status Readback

After applying the status update:

```text
thread_33=resolved
design_open=23
announcements_open=3
general_open=2
open_total=34
```

The forum status change was made through the existing MCP
`forum_set_thread_status` tool using:

```text
forum_set_thread_status(thread_id=33,status=resolved)
```

## What This Does Not Claim

This closeout does not claim the true two-node hardware wet-test was completed.
It preserves the owner's recorded distinction:

- merge logic is e2e-validated and currently implemented;
- the real hardware wet-test is deferred and runbook-ready;
- a future interactive aio2/Mac coordination window can still run the runbook;
- any future LWW-loss evidence should reopen the lane with sync logs and SQL
  readback.

The older tech-debt note about the hardware wet-test gap should therefore be
read as a deferred validation opportunity, not as a reason for `#33` to remain
an active open planning thread.

## Rollback

The status change is reversible:

```text
forum_set_thread_status(thread_id=33,status=open)
```

The closeout post `#2835` should remain as an audit note if the thread is
reopened.

## Next Board-Hygiene Candidates

Next board-hygiene work should stay thread-specific and avoid sweeping older
boards in bulk.

Reasonable future candidates:

- `#26` security announcement, only with owner/security sign-off because
  keeping security notices open may be intentional;
- one of the older design threads with an explicit terminal decision in its
  tail, after a focused read and rollback note.

## Boundary

This pass did not:

- change memory-sync code, import policy, wrapper contents, systemd units,
  runtime flags, deployed binaries, DB schema, memory rows, memory graph edges,
  retrieval ranking, tool routing, prompts, profiles, or MCP exposure;
- run a true two-node wet-test;
- run sync against remote peers;
- deploy a binary or restart services;
- close `#26` or any security announcement.

The only live state mutation was the forum thread status update for `#33`.
