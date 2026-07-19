# Engram G1.4 WASI G2F — public synthetic build authorization

Date: 2026-07-19

Gate: `G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION`

Mode: public decision; no manifest change, no build, no run in this gate.

## Owner decision

The owner's explicit authorization recorded in forum #4774 opens exactly one
successor: `G2G_PUBLIC_SYNTHETIC_HOST_BUILD`.  G2G may compile only the already
reviewed G2E logical-clock host model.  It is intentionally a smaller proof
than a component/linker build: no WIT binding generation, Wasmtime dependency,
broad WASI linker, component artifact, or execution is in scope.

G2F itself is documentation and static enforcement only. It does not add a
manifest or lockfile, resolve/install/promote a dependency, invoke Cargo,
access a candidate/private/capability input, or change runtime, MCP, policy,
deployment, canary, or G1.4.

## G2G allowlist and command

Only the following future files may be created or changed:

1. `scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.toml`
2. `scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.lock`
3. `scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/src/lib.rs`
4. bounded G2G checker, receipt producer, docs, and README entry.

The fixture manifest must be an isolated `[workspace]`, package
`engram-g14-wasi-g2g-host-build` at version `0.1.0`, edition `2021`,
`rust-version = "1.85"`, with no dependencies. Its library must re-export the
unchanged G2E host source via an explicit `#[path]` reference. The only allowed
build command is equivalent to:

```sh
CARGO_NET_OFFLINE=true cargo build --offline --locked \
  --manifest-path scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.toml \
  --target-dir "$TMPDIR/engram-g2g-host-build"
```

The target directory must be temporary and removed after hashing the produced
library. Build success proves only that exact public host source compiles with
the declared local toolchain; it is not behavioral proof and never authorizes
execution.

This decision does not authorize execution.

## Prohibitions and stop conditions

G2G must fail closed if Cargo needs a network fetch, lockfile changes during a
`--locked` build, a dependency appears, the re-export path is altered, the
source digest differs from G2E, the output is missing, or an ambient/broad-WASI
path appears. It must not run tests, examples, binaries, components, or the
output; it must not use native/QEMU fallback. Any failure preserves the branch
and grants no next authority.

The only successor of a G2G compile receipt is a separate owner-gated decision
for WIT/component/linker dependency authorization. G2G cannot authorize that
dependency boundary or any execution.
