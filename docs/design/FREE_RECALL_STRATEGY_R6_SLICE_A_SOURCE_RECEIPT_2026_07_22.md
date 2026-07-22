# Free Recall Strategy R6 — Slice A Source Receipt

Date: 2026-07-22

Status: **SOURCE LANDED / STATIC PASS / FEATURE BUILD UNVERIFIED**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R6_SLICE_A_SOURCE_PREREGISTRATION_2026_07_22.md`

Source commit: `99a83d65`

## 1. Landed source

R6 Slice A adds one private `ab-store` module behind the default-off
`episode-observation-slice-a` feature. The feature reuses the crate's existing
optional `ring = 0.17` dependency and is absent from the default feature list.

The module contains only:

- borrowed key material and an internal key-provider trait;
- exact R5 epoch and memory-key validation;
- full-length, length-framed HMAC-SHA-256 item-reference derivation;
- pure episode event/source types;
- a no-op sink that returns `Disabled`;
- five source-level public-synthetic unit tests.

It contains no SQLite, filesystem, environment, async runtime, MCP, retrieval,
sync/export, telemetry, network, clock, producer, or BioCortex reference.

## 2. Static evidence

- local exact-file `rustfmt --check`: pass;
- local forbidden-import scan: pass;
- R5 Python parent-contract self-test: pass;
- `git diff --check`: pass;
- default feature list unchanged;
- `ring` remains optional;
- no Cargo.lock change and no new dependency declaration;
- local source SHA-256:
  `b5a40dceefce4d2a44ded0c4de59d84a27c4e13e4ba866017ceee79d169490bc`;
- tb14 fetched the remote commit and produced the identical source SHA-256.

tb14 does not have `rustfmt`, so no independent formatting claim is made.

## 3. Build-boundary incident

The source-only preregistration prohibited Cargo execution. The agent did not
invoke Cargo directly, but the repository's pre-commit hook automatically ran:

```text
cargo check -p ab-bridge --all-targets --quiet
```

because the staged commit contained Rust/Cargo files. This was outside the
planned authority boundary and is recorded rather than laundered as evidence.
The new module is behind a non-default feature, so that default-feature check
did not compile or test R6 Slice A. It emitted two pre-existing warnings and
returned success.

No further Cargo command was run.

## 4. Claim boundary

The source is formatted and statically isolated, but its feature has not been
compiled and its five Rust tests have not run. Therefore R6 is not accepted as
working code yet.

This receipt does not authorize SQLite Slice B, producer Slice C, a production
key provider, runtime configuration, private data, merge, or deployment.

## 5. Next gate

The next separately authorized action should be a public-source feature build
and test only:

```text
cargo check -p ab-store --no-default-features --features episode-observation-slice-a
cargo test -p ab-store --no-default-features --features episode-observation-slice-a episode_observation_slice_a
```

Run locally first and then on a Rust-equipped independent node. Passing that
gate would verify Slice A only and would not open Slice B.

