# Engram G1.4 WASI toolchain tuple review draft

Date: 2026-07-21

Status: **draft proposed; awaiting owner signature; no authority**.

## Recommendation

Use Rust/Cargo 1.94.0 as the candidate tuple anchor. It matches the existing
G2A public-static Rust pin and the current local observation. The previously
recorded Rust/Cargo 1.92.0 is retained as historical evidence only; it must not
be silently substituted or upgraded during execution.

This recommendation is not a selection authorization. The candidate remains
incomplete because `wasm-tools`, `wit-bindgen`, `cargo-component`, `wasm-ld`,
and a usable Wasmtime executable identity were not observed. The adapter,
cache roots, exact commands, bounded output roots, and expected hashes are
also unset.

## Canonical contract

The tuple binds the actual WIT bytes at
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, SHA-256
`d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be`:
`agent-bridge:g14-clock-probe/probe@0.1.0`, export
`typed-report: func() -> typed-report`, and the ordered `u64` record fields.

## Signature boundary

The fixture intentionally contains nulls and `false` authority flags. An owner
signature may only be added after an independent reviewer freezes every tool
path/version/hash, adapter, dependency/cache tuple, command allowlist,
work/output roots, expected artifact/import-manifest hashes, cleanup and
rollback receipts, and network/private-input prohibition. No checker PASS,
commit, merge, or tool presence can substitute for that signature.

Until then the lane stops at this draft and remains fail closed.
