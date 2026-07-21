# Engram G1.4 WASI G2L WIT/ABI Contract Reconciliation

Date: 2026-07-21
Status: `RESOLVED — TYPED_REPORT CANONICAL; HISTORICAL RECONCILIATION RECORD`

The reconciliation was resolved by the owner decision to use the observed
`typed-report` WIT contract. The final build, runtime, deployment, and live
MCP evidence are indexed by
`ENGRAM_G1_4_WASI_G2L_STATUS_CONVERGENCE_AND_BUSINESS_COMPONENT_CONTRACT_2026_07_21.md`.
The remainder of this file is retained to explain the former mismatch and is
not an active blocker or authorization gate.

## Purpose and authority boundary

This is a static blocking packet bound to execution-draft baseline commit
`4db84d614fdff3430a664d1bec8627780ce99168` and tree
`d535e7b9bea5268713374ab4569c70a92c5f066b`. It records only already observed
facts. It performs no WIT parsing, dependency resolution, generation, build,
link, execution, runtime operation, or deployment, and grants none of those
authorities.

## Observed contract

The only observed WIT source path is
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, with
SHA-256 `d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be`.
Its observed declarations are:

- package `agent-bridge:g14-clock-probe@0.1.0`;
- world `probe`;
- export `typed-report: func() -> typed-report`;
- imports `wasi:clocks/wall-clock@0.2.12`,
  `wasi:clocks/monotonic-clock@0.2.12`, and `wasi:io/poll@0.2.12`.

No ABI SHA, generated bindings, adapter, or component was observed.

## Reconciliation blocker

The older preregistration expects export
`agent-bridge:g14-clock-probe/probe.run@0.1.0` with result
`deterministic-clock-report-v0`. Those expectations do not match the observed
WIT contract above. Therefore the status is
`CONTRACT_RECONCILIATION_REQUIRED`. WIT generation and component/linker build
remain prohibited; execution, runtime, and deployment remain prohibited.

G2A `wasmtime=46.0.1` is recorded only as an observed candidate. It does not
authorize parsing or dependency resolution. Direct `rustc` and Cargo `1.92.0`
were observable. `wasm-tools`, `wit-bindgen`, `cargo-component`, and `wasm-ld`
were `NOT_FOUND`. These observations do not open any authority.

## Only allowed successor

The owner must choose the canonical WIT contract and separately approve its
revision. This packet must not automatically modify the older preregistration
and must not execute any tool. Until that distinct approval, every gated
authority remains closed.

## Static integrity

The fixture binds exactly this document, the fixture, the checker, and the
wrapper using SHA-256 after replacing every lowercase 64-hex sequence in each
file with 64 zeroes. The checker is Python standard-library only, launches no
process, uses no network, and performs no build. The wrapper only invokes the
checker.
