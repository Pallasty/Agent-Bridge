# Engram G1.4 WASI G2L — component-build result

This receipt records the narrowly authorized WIT-bindings, linker, and
component-build probe for the canonical G2E WIT contract. It is a build-only
result. No generated component was executed, attached to Agent-Bridge, or
deployed.

## Scope and authority

- authorization: owner approval in the active session, 2026-07-21;
- allowed: WIT binding generation, core-Wasm compilation needed by the
  component linker, and component encoding/validation;
- not allowed and not performed: component execution, host/runtime
  integration, Agent-Bridge source integration, deployment, or production
  resource access;
- isolated build root: `/Users/pallasting/Projects/g14-component-build.vYPFW4`;
- repository baseline: `dfa6a2ad2a5ca8b21680ac65af43925187ab2a7f`.

## Contract inputs

The source contract is
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`.

| item | SHA-256 |
|---|---|
| canonical `world.wit` | `d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be` |
| pinned `wasi:clocks@0.2.12` source | `6ed8aa65bb8cbe224a0b2cbac9fc1b3bd25bdb17eda5ae0d23c983ed31c447cc` |
| pinned `wasi:io@0.2.12` source | `96e206d00076fa0480df32c5bcf255a3fa4862805ac2f6b8537a781cce54f433` |
| generated Rust bindings | `e2e064d36cb7b7697ad97535fb26f3bd162d80d132e13675ef23ef95d5053ba3` |
| temporary Rust manifest | `7bd0076bf7af227a748ffa7aa79e0d137eb03192f3249f7c193464a028e2f9e8` |
| temporary Cargo.lock | `57727312f3375b964b1ec9117701010fd8b8a12e7c63b92c6730af643baf2c5c` |

The bindings were generated with `wit-bindgen 0.58.0`, using the fully
qualified world `agent-bridge:g14-clock-probe/probe@0.1.0` and
`--generate-all`. The core guest was compiled for `wasm32-unknown-unknown`
because the first direct `wasm32-wasip2` attempt did not retain the imported
WIT interfaces in the resulting component. The final core module was then
encoded by `wasm-tools component new`.

## Build evidence

| artifact | result |
|---|---|
| core guest (`wasm32-unknown-unknown`, release) | `524ed8d69f0ed785ef3cf131334ec8b3c291920a4ff4bc5651aefcd74d6e7131` |
| component (`wasm-tools component new`) | `0b20cc46741a5a9a99a75f67c4c56bf1632b7f398162aa5b8eadd15c08c7642b` |
| `wasm-tools validate` | PASS |
| extracted component WIT imports | `wasi:clocks/wall-clock@0.2.12`, `wasi:clocks/monotonic-clock@0.2.12`, `wasi:io/poll@0.2.12` |
| extracted export | `typed-report: func() -> typed-report` |
| extracted record fields | `wall-epoch-seconds: u64`, `logical-nanoseconds: u64`, `quantum-nanoseconds: u64` |

The component WIT contains exactly the three expected WASI imports and the
typed report export. The linker may reorder the imports in the extracted
representation; the semantic import set and versions match the canonical
source.

## Native cargo-component status

`cargo component build` was also probed in the isolated package, but it did
not produce a component. With `--offline --locked`, the temporary package
was rejected because its lockfile was not accepted by that command path. A
normal isolated attempt then failed while constructing the target world:
`package 'wasi:clocks@0.2.12' not found`. This is a local WIT-dependency
resolution problem, not evidence against the successful direct
`wit-bindgen` + `wasm-tools` linker path.

The owner selected the structural G2L contract. The native `cargo-component`
packaging issue remains a separate, explicitly scoped follow-up and does not
block this G2L result.

## Package identity caveat

`wasm-tools component wit` reports the top-level emitted package as
`root:component`. The embedded source/bindings still use the canonical
`agent-bridge:g14-clock-probe@0.1.0` package and `probe` world, while the
linker-generated component's structural world is anonymous. This is recorded
as a contract caveat, not silently treated as an exact nominal-package match.
The owner selected the first acceptance mode:

1. **selected:** structural G2L acceptance (imports, versions, export, and
   record types);
2. not selected: strict nominal-package acceptance, which would require a
   linker/packaging path that preserves `agent-bridge:g14-clock-probe@0.1.0`
   at the component top level.

Until that choice is made, the evidence status is:

**G2L STRUCTURAL ACCEPTED — NATIVE_CARGO_COMPONENT_UNRESOLVED (NON-BLOCKING FOLLOW-UP)**
