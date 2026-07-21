# Engram G1.4 WASI toolchain tuple review draft

Date: 2026-07-21

Status: **draft proposed; awaiting owner signature; no authority**.

## Recommendation

Use Rust/Cargo 1.94.0 as the candidate tuple anchor. It matches the existing
G2A public-static Rust pin and the current local observation. The previously
recorded Rust/Cargo 1.92.0 is retained as historical evidence only; it must not
be silently substituted or upgraded during execution.

This recommendation is not a selection authorization. The five public tool
identities have now been installed in the isolated prefix
`/Users/pallasting/.local/share/agent-bridge/g2a-toolchain-20260721/bin` and
verified by version output and local SHA-256. The selected observations are
wasm-tools 1.252.0, wit-bindgen-cli 0.58.0, cargo-component 0.20.0, Wasmtime
46.0.1, and LLD/wasm-ld 21.1.8. The cargo-component release API supplied no
published digest, so its local digest is explicitly not treated as a vendor
signature.

The adapter, cache roots, exact commands, bounded output roots, and expected
artifact/import-manifest hashes are still unset. The tuple therefore remains
incomplete and cannot be signed for execution.

## Canonical contract

The tuple binds the actual WIT bytes at
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, SHA-256
`d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be`:
`agent-bridge:g14-clock-probe/probe@0.1.0`, export
`typed-report: func() -> typed-report`, and the ordered `u64` record fields.

## Signature boundary

The fixture contains the observed tool paths/version/hashes but retains nulls
for the unreviewed execution fields and `false` authority flags. An owner
signature may only be added after an independent reviewer freezes every tool
path/version/hash, adapter, dependency/cache tuple, command allowlist,
work/output roots, expected artifact/import-manifest hashes, cleanup and
rollback receipts, and network/private-input prohibition. No checker PASS,
commit, merge, or tool presence can substitute for that signature.

Until then the lane stops at this draft and remains fail closed.
