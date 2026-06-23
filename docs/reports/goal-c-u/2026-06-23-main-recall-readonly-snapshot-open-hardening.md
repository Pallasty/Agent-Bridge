# Main Recall Read-Only Snapshot Open Hardening

Date: 2026-06-23
Host: `aio2`
Worktree: `/Data/CascadeProjects/agent-bridge`
Base: `6d6f7c8` (`docs(memory): design trigger baseline acceptance gate`)
Scope: eval-harness safety hardening; no production retrieval change

## Why

The frozen-baseline reports carried a known caveat: `recall_eval` could be
pointed at a caller-pinned `AB_BASELINE_DB`, but the main `SqliteStore::open`
path still performed writable store initialization:

- create parent directory;
- set `PRAGMA journal_mode=WAL`;
- run schema creation and migrations.

That is acceptable for the live default store, but it is the wrong shape for a
frozen snapshot gate. A pinned snapshot comparison should open the database as
read-only and avoid migration/WAL initialization.

## What Changed

`ab-store` now exposes:

```rust
SqliteStore::open_read_only(path)
```

The read-only path:

- uses SQLite `SQLITE_OPEN_READ_ONLY`;
- does not create parent directories;
- does not run schema creation or migrations;
- does not set `journal_mode=WAL`;
- sets `PRAGMA query_only=ON` and `PRAGMA foreign_keys=ON`;
- keeps the same query APIs available for eval reads.

`crates/bridge/examples/recall_eval.rs` now chooses the store-open path from
the baseline source:

- default live store: `SqliteStore::open`;
- `AB_BASELINE_DB`: `SqliteStore::open_read_only`.

The harness prints the selected open mode:

```text
# baseline db open mode: writable live default (legacy store init)
# baseline db open mode: read-only pinned snapshot (no migration/WAL init)
```

## Verification

Targeted store regression:

```sh
cargo test -p ab-store read_only_open_does_not_create_missing_parent_dir -- --nocapture
```

Result:

```text
1 passed
```

The regression asserts that read-only open fails on a missing DB path without
creating the missing parent directory.

Recall eval tests:

```sh
cargo test -p ab-bridge --example recall_eval -- --nocapture
```

Result:

```text
29 passed
```

Examples check:

```sh
cargo check -p ab-bridge --examples
```

Result: passed.

Pinned-path smoke:

```sh
AB_BASELINE_DB=/tmp/.../state.snapshot.test.db \
  cargo run -p ab-bridge --example recall_eval
```

Header:

```text
baseline db source: AB_BASELINE_DB (caller-pinned DB)
store fingerprint: pinned=true active=452 edges=572 newest=1782210638
baseline db open mode: read-only pinned snapshot (no migration/WAL init)
```

The smoke used a temporary copy of the local live DB only to exercise the
read-only code path. It is not canonical recall evidence.

## Decision

The snapshot-open hardening gate is landed for `recall_eval`:

- pinned `AB_BASELINE_DB` no longer goes through writable migration/WAL init;
- live default behavior remains unchanged;
- production/default `memory_search` remains unchanged;
- pinned Mac replay is now less likely to perturb the snapshot being measured.

Remaining caveat: this is a read-only SQLite open, not a full immutable-URI
snapshot protocol. If later evidence shows sidecar files are still a problem on
specific SQLite/WAL snapshots, the next hardening layer should use an
`immutable=1` URI or a copied rollback-journal snapshot artifact.
