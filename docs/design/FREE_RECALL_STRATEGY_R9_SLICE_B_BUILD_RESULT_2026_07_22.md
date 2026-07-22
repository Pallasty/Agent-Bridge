# Free Recall Strategy R9 — Slice B Build Result

Date: 2026-07-22

Status: **LOCAL BUILD GATE PASS / INDEPENDENT-NODE RECHECK PENDING**

Source receipt:
`docs/design/FREE_RECALL_STRATEGY_R8_SLICE_B_SOURCE_RECEIPT_2026_07_22.md`

Source commit under test: `1d09b06c`

## 1. Verdict

The default-off Slice B feature compiles and all five targeted public-source
tests pass on the local macOS node. A second detached clean-worktree rerun,
using the exact same commit, offline locked dependencies, and a separate target
directory, also passes.

This accepts the local build/test gate only. It does not claim independent-node
reproducibility: both configured candidates (`aio2` and `tb14`) currently fail
SSH host-key verification before any remote command can run. No new key was
accepted and no remote worktree was created.

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
| independent aio2/tb14 | not run: unverified SSH host keys | — | — |

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

Before treating Slice B as independently accepted, an owner-verified SSH host
key (or another separately trusted independent node) is required for the same
offline locked rerun. Even after that, the next functional lane is still a
separate authorization for a single producer seam; R9 does not enable one.
