# Free Recall Strategy R6 — Slice A Build Result

Date: 2026-07-22

Status: **BUILD GATE PASS / SLICE A ACCEPTED / SLICE B NOT OPEN**

Source receipt:
`docs/design/FREE_RECALL_STRATEGY_R6_SLICE_A_SOURCE_RECEIPT_2026_07_22.md`

Source commit under test: `33a3e95e`

## 1. Verdict

R6 Slice A compiled and passed all five filtered public-source unit tests on
the local macOS node and on an isolated aio2 Linux worktree. The default-off
feature's pure types, HMAC-SHA-256 item-reference derivation, fail-closed key
provider boundary, and no-op sink are accepted at the Slice A boundary.

This result does not open SQLite Slice B, producer Slice C, real capture,
retrieval, a production key provider, merge to master, or deployment.

## 2. Exact gate

Both accepted runs used the repository-pinned Rust/Cargo `1.96.0` and the
following feature-isolated commands:

```text
cargo check --locked -p ab-store --no-default-features \
  --features episode-observation-slice-a
cargo test --locked -p ab-store --no-default-features \
  --features episode-observation-slice-a episode_observation_slice_a
```

The independent final rerun also used `--offline`, proving that its concluding
check/test consumed only the locked dependency cache.

## 3. Results

| Node | Platform | Toolchain | Check | Tests |
| --- | --- | --- | --- | --- |
| local | macOS arm64 | Rust/Cargo 1.96.0 | pass | `5 passed, 0 failed` |
| aio2 | Linux x86_64 | Rust/Cargo 1.96.0 | pass | `5 passed, 0 failed` |

The five tests cover:

- the public-synthetic HMAC known answer;
- missing provider and unknown/invalid epoch abstention;
- weak key and empty/oversized memory-key rejection;
- epoch and memory-key binding;
- no-op sink `Disabled` disposition.

Both worktrees remained clean and the aio2 detached build worktree and temporary
target directories were removed after verification.

## 4. Warnings

The feature build emits dead-code warnings because Slice A deliberately has no
runtime consumer yet. These warnings are evidence of the current isolation and
were not suppressed. The build also repeats existing unrelated warnings in
`sqlite.rs` and `vector.rs`.

No warning indicates a test failure, unsafe fallback, serialization of key
material, or runtime activation.

## 5. aio2 environment side effect

The first aio2 invocation used the directory-selected rustup wrapper. Its
installed `1.96.0` entry was incomplete, and rustup automatically synchronized
and completed that toolchain before the SSH result stream returned. Cargo also
updated the public crates.io index and populated its user cache when the first
offline attempt lacked a workspace dependency index entry.

This was an environment-side effect of the authorized public-source build, not
a repository change. It is recorded explicitly. The final accepted aio2 run
used explicit `rustup run 1.96.0`, `--offline`, and `--locked`.

No system package was installed, and no attempt was made to undo the completed
toolchain because that could disrupt other aio2 tasks.

## 6. Next gate

The next admissible research target is a Slice B migration and inert-adapter
preregistration. It must choose the schema version current at implementation
time, use disposable databases only, prove default-off zero effects and inert
rollback, and remain disconnected from `memories`, retrieval, sync/export, and
all producers.

R6 completion does not itself authorize that design or source work.
