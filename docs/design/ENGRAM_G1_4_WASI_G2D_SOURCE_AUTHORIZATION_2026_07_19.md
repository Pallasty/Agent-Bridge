# Engram G1.4 WASI G2D source authorization

Date: 2026-07-19

Gate: `G2D_PUBLIC_SOURCE_AUTHORIZATION_DECISION`

Mode: public decision; no source/no build/no run in this gate

## Owner decision

The owner explicitly authorized the transition after G2C B0 completion. The
authorization opens exactly one successor:
`G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING`.

It authorizes public, synthetic source authoring only. It does not authorize a
Cargo workspace change, dependency selection/install/promotion/compile,
component build or execution, downloaded-binary execution, candidate/private
or capability access, runtime/store/MCP/policy/deployment/canary/G1.4 change,
or a native/QEMU fallback.

## G2E source allowlist

Only these future source paths may be created or changed by G2E:

1. `scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`
2. `scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/component/src/lib.rs`
3. `scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs`

No `Cargo.toml`, lockfile, binary, generated binding, or runtime path is in
the allowlist. G2E may add its own bounded checker/producer/docs/receipt only
to prove the source text and its path surface; those tools must never compile,
run, install, or promote anything.

## Required source shape

The future WIT world is the frozen public probe world
`agent-bridge:g14-clock-probe/probe@0.1.0`. It may import exactly, and in this
order:

1. `wasi:clocks/wall-clock@0.2.12`
2. `wasi:clocks/monotonic-clock@0.2.12`
3. `wasi:io/poll@0.2.12`

The component and host must remain synthetic, bounded, and public. Host source
must express direct wall-clock now/resolution, monotonic now/resolution and
deadline subscription, and `io/poll` readiness over one logical-clock state.
The source-level evidence must reject broad `wasmtime-wasi`/`wasmtime-wasi-io`
linkers, Tokio time/sleep/instant, `WasiCtxBuilder`, ambient host clocks/sleep,
network/filesystem/stdio/random/HTTP/preview1 imports, and native/QEMU
fallback. A textual check is B1 source evidence, not compiled proof.

## B1 and later gates

G2E must freeze source digests and produce static proof that the allowlist and
forbidden-path rules hold. Its passing result reaches only
`POST_SOURCE_PRE_BUILD_EVIDENCE_COMPLETE_AWAITING_OWNER_BUILD_AUTHORIZATION`.
It must not build. Any source mutation invalidates B1 and B2.

The next build decision is a separate owner gate, provisionally
`G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION`. Build authorization would
not authorize execution; execution remains a separate owner gate after B2.

## Stop conditions

Immediately fail closed and stop the G2E lane if any source target falls
outside the allowlist, if a manifest/lockfile/dependency/runtime path is
changed, if a forbidden host path appears, if source text is generated from
candidate/private material, or if static proof is ambiguous. Do not substitute
native/QEMU behavior. Record the failure and preserve the branch for review.
