# Free Recall Strategy R9 — Slice B Build Result

Date: 2026-07-22

Status: **BUILD GATE PASS / SLICE B ACCEPTED / PRODUCER NOT OPEN**

Source receipt:
`docs/design/FREE_RECALL_STRATEGY_R8_SLICE_B_SOURCE_RECEIPT_2026_07_22.md`

Source commit under test: `1d09b06c`

## 1. Verdict

The default-off Slice B feature compiles and all five targeted public-source
tests pass on the local macOS node and on an isolated aio2 Linux worktree. A
second local detached clean-worktree rerun, using the exact same commit, offline
locked dependencies, and a separate target directory, also passes.

The initial `ssh aio2` attempt failed because `known_hosts` binds the existing
trusted ED25519 key to Tailnet IP `100.93.4.56`, not the DNS label. Tailscale
confirmed that IP currently belongs to aio2; the accepted run used
`pallasting@100.93.4.56`. No new host key was accepted or replaced.

## 2. Exact accepted commands

```text
cargo check --locked -p ab-store --no-default-features \
  --features episode-observation-slice-b
cargo test --locked -p ab-store --no-default-features \
  --features episode-observation-slice-b episode_observation_slice_b -- --nocapture
```

The clean-worktree rerun used the same commands with `rustup run 1.96.0`,
`--offline`, `--locked`, an exact detached checkout of `1d09b06c`, and an
isolated temporary target directory.

## 3. Results

| Evidence | Toolchain | Check | Slice B tests |
| --- | --- | --- | --- |
| local worktree | Rust/Cargo 1.96.0, macOS arm64 | pass | `5 passed, 0 failed` |
| detached clean worktree | Rust/Cargo 1.96.0, macOS arm64, offline+locked | pass | `5 passed, 0 failed` |
| independent aio2 | Rust/Cargo 1.96.0, Linux x86_64, offline+locked | pass | `5 passed, 0 failed` |

The five tests cover fresh v44 creation, v43→v44 upgrade, collision rollback
without cursor advance, disabled gate no-write behavior, and exact finalized
open/item/close projection.

## 4. Build findings and corrections

The first check exposed a missing lifetime on the borrowed `item_ref` returned
by the event-shape helper. The first test compile then exposed three ambiguous
`tokio_rusqlite::Connection::call` error types. Both were corrected in
`1d09b06c`, and the accepted runs above compile and execute the corrected
source.

Warnings are expected default-off dead-code warnings for Slice A/B (they have
no runtime caller), plus one pre-existing mixed-script warning in `sqlite.rs`.
No warning indicates a failed test, runtime activation, or unexpected producer
path.

## 5. Scope and next authority

Only temporary disposable databases created by tests were opened. No user
`state.db`, real producer, runtime configuration, retrieval path, sync/export,
merge to master, or deployment was used.

The aio2 detached worktree and exact temporary target directory were removed
after the successful command chain; post-run inspection found zero matching
worktrees and zero matching temporary paths.

Slice B is accepted at its build/test boundary. The next functional lane is a
separate authorization for a single producer seam; R9 does not enable one.
