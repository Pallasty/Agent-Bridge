# Engram G1.4 G2A canonical WIT and tooling preflight

Date: 2026-07-21

Status: **read-only observation; fail closed; no authority**.

## Decision

The canonical contract is the actual public WIT at
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, not a
reconstructed export name. Its SHA-256 is
`d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be` and its
export is `typed-report: func() -> typed-report`, with the three ordered
`u64` record fields recorded in the fixture.

The local preflight found Rust/Cargo 1.94.0 at the observed `.cargo/bin`
paths, while the landed G2L draft froze an earlier direct observation of
Rust/Cargo 1.92.0. This is tool identity drift, not permission to upgrade.
`wasm-tools`, `wit-bindgen`, `cargo-component`, `wasm-ld`, and `wasmtime` were
not found. The tuple is therefore not ready for signing and the gate remains
fail closed.

## Boundary

This receipt records observations only. It does not select a toolchain, install
or download anything, authorize dependencies, generate bindings, compile a
component, execute a component, alter runtime behavior, or deploy. A future
owner-signed tuple must explicitly choose the Rust release, binding/component
tool, adapter, linker, dependency/cache roots, exact commands, and output
hashes. Missing tools cannot be filled by PATH discovery or an implicit
installation.

## Verification

```bash
scripts/check-engram-g14-wasi-g2a-canonical-preflight.sh
```

The checker uses only Python's standard library and checked-in bytes. Its
mutation tests reject canonical WIT drift, export/record drift, tool presence
overclaims, tool-version drift, authority changes, and negative-evidence
overclaims. A passing checker is evidence integrity only; it is not execution
authority.
