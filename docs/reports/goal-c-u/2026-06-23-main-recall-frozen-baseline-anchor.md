# Main Recall Frozen Baseline Anchor

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `251ad52` (`test(memory): add case2 tool surface positive controls`)
Scope: eval-only gate hygiene

## Why

Forum #3929 caught a real measurement problem: the standing `recall_eval`
hard-tier runtime gate reads the live Mac memory store by default. The corpus is
fixed, but the store content is not. That means future before/after
runtime-lift claims can be contaminated by unrelated memory writes, access
changes, or additional rows.

Forum #3934 then made the next requirement concrete: every cited hard-tier
anchor needs store identity, and the review target set should follow the pinned
baseline's actual hard misses. This slice accepts that direction.

## Harness Change

`crates/bridge/examples/recall_eval.rs` now prints DB context before it opens the
store:

```text
# baseline db source: default_db_path (live local store)
# baseline db path: /Users/pallasting/Library/Application Support/agent-bridge/state.db
# baseline db bytes: 1237393408
# store fingerprint: pinned=false active=3024 edges=5534 newest=1782205902 path=/Users/pallasting/Library/Application Support/agent-bridge/state.db
# WARNING: live store baseline is drift-prone; set AB_BASELINE_DB=<frozen snapshot> for canonical runtime-gate comparisons
# baseline db note: live store is drift-prone; use AB_BASELINE_DB for before/after runtime gates
```

When `AB_BASELINE_DB` is set to the #3934 snapshot, the same harness prints:

```text
# baseline db source: AB_BASELINE_DB (caller-pinned DB)
# baseline db path: /Users/pallasting/Library/Application Support/agent-bridge/snapshots/state.snapshot.20260623.db
# baseline db bytes: 1150271488
# store fingerprint: pinned=true active=3022 edges=5527 newest=1782205313 path=/Users/pallasting/Library/Application Support/agent-bridge/snapshots/state.snapshot.20260623.db
# baseline db note: caller controls DB contents; compare before/after against the same snapshot
```

The review target set changed from stale `#1/#2/#5/#9/#14` to the pinned
baseline hard-miss set `#1/#2/#8/#9/#14`.

The change is reporting and gate-target hygiene only. It does not change the
retrieval modes or ranking formulas.

## Frozen Snapshot

Accepted #3934 snapshot source:

```text
/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
```

`~/.local/share/agent-bridge` is a symlink to:

```text
/Users/pallasting/Library/Application Support/agent-bridge
```

Pre-run verification:

```text
integrity_check: ok
active memories: 3022
memory edges: 5527
newest_created_at: 1782205313
sha256 before this harness run: de9a969823156d442cb60ef69b8eef9e6c4b55cd31fde83d1c8f80abdc886bb2
```

Important finding: current `SqliteStore::open` enables WAL and can touch the
snapshot file even for this eval command. After running the harness, the
snapshot directory contained a `state.snapshot.20260623.db-wal` file and the
main DB file hash changed, while the logical fingerprint stayed:

```text
active memories: 3022
memory edges: 5527
newest_created_at: 1782205313
```

Therefore the canonical comparison identity for this v1 gate is the harness
fingerprint plus the hard-tier gate output, not the bare DB-file hash after the
file has been opened by the current store layer. A future hardening slice can
add a true read-only store-open path or a managed working-copy flow.

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
git diff --check
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo check -p ab-bridge --all-targets
cargo run -p ab-bridge --example recall_eval
AB_BASELINE_DB=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db \
  cargo run -p ab-bridge --example recall_eval
```

Example tests:

```text
16 passed; 0 failed
```

Live current hard-tier anchor:

```text
## Runtime gate anchor (main recall_eval hard tier)
  hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
  hard fts misses: 5 case(s) -> #1, #2, #8, #9, #14
  hard zero-row fts misses: 2 case(s) -> #1, #2
  hard fts+graph added hits over fts misses: 0 case(s)
```

Frozen current hard-tier anchor:

```text
## Runtime gate anchor (main recall_eval hard tier)
  hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
  hard fts misses: 5 case(s) -> #1, #2, #8, #9, #14
  hard zero-row fts misses: 2 case(s) -> #1, #2
  hard fts+graph added hits over fts misses: 0 case(s)
```

Two consecutive `AB_BASELINE_DB=... cargo run -p ab-bridge --example
recall_eval` executions produced identical hard-tier runtime-gate lines for the
pinned snapshot.

## Read

The #3929/#3934 concern is accepted and now has a concrete gate workflow:

1. create or choose a frozen DB snapshot;
2. record integrity and logical fingerprint (`active`, `edges`,
   `newest_created_at`);
3. run the baseline harness with `AB_BASELINE_DB=<snapshot>`;
4. apply a proposed runtime retrieval change;
5. run the same command against the same snapshot or same working copy;
6. claim lift only if the main hard-tier anchor moves while the store
   fingerprint remains unchanged.

Current measured values match between the live store and the pinned snapshot in
this run. The important change is not a metric improvement; it is that later
proposals have a visible store identity and no longer need to treat a live-store
number as canonical.

## Residual Risk

The frozen snapshot removes store-content drift from the comparison only when
the store fingerprint is held constant. It does not prove every retrieval mode
is fully deterministic. In this run, consecutive full-output frozen runs showed
small `hybrid` rank/MRR jitter outside the hard-tier gate, while the hard-tier
runtime-gate lines stayed identical.

The current store API also opens the DB through the normal writable path, which
can create WAL state on the snapshot. That is acceptable for this eval-only
gate-hygiene slice because active memory count, edge count, newest timestamp,
and hard-tier output remained stable; it is not a final read-only snapshot
contract.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, deploy
behavior, or the production memory store. It only makes the eval DB source and
store fingerprint explicit, updates the review target set to the pinned hard
misses, and documents the frozen-baseline workflow for the next runtime
proposal.
