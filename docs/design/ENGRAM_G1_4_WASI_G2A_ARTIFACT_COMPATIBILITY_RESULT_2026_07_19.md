# Engram G1.4 G2A artifact compatibility result

Date: 2026-07-19

Verdict:
**`G2A_FAIL_CLOSED_UNSATISFIABLE_ARTIFACT_ORDER_NO_SOURCE_NO_BUILD_NO_RUN`**.

No authority.

Public static evidence closes the exact minimal Wasmtime dependency graph, a
complete evidence-only lockfile, crates.io payload checksums, Rust 1.94.0 target
and toolchain pins, and a pinned bounded RustSec scan with zero findings. It
also confirms source-level support for exact-world bindings and confirms that
Wasmtime's broad WASIp2 clock subscriptions use Tokio timer paths.

The gate cannot pass as ordered. G2 requires component/host source digests and
a component binary/import-manifest digest before source or build may occur, and
Wasmtime v46.0.1 publishes no matching custom-clock component. The source
archive's official immutable digest is pinned, but a local full-byte transfer
did not complete; WIT ABI compatibility and timer bypass remain uncompiled and
conditional. All authority therefore remains closed.

No official `cargo-audit` receipt is claimed; that review must be repeated
before any dependency promotion.

The only permitted successor is the public-static, no-run
`G2B_PUBLIC_WASI_ARTIFACT_ORDERING_REPAIR_PREREGISTRATION`. It may split the
causally impossible single barrier into pre-source, pre-build, and pre-run
barriers. It does not authorize source, build, run, dependency/runtime
promotion, candidate/private access, deployment, canary change, or G1.4.
