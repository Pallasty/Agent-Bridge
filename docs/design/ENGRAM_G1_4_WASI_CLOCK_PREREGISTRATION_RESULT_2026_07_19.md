# Engram G1.4 G2 WASI custom-clock preregistration result

Date: 2026-07-19

Verdict: **`WASI_CUSTOM_CLOCK_ROUTE_PREREGISTERED_NO_BUILD_NO_RUN_NO_AUTHORITY`**.

The static contract pins Wasmtime `46.0.1`, its exact public crate checksums,
the vendored `wasi:clocks@0.2.12` and `wasi:io@0.2.12` packages, and six critical
upstream source hashes as review targets only. No dependency was adopted or
installed.

The review closed an important design gap: replacing Wasmtime's monotonic
`now()` provider does not replace its built-in Tokio-backed timer subscriptions.
The future harness must therefore bind only the exact wall-clock,
monotonic-clock, and poll interfaces and directly implement `now`, both
subscription methods, and deterministic poll over one logical-clock state.
Broad WASI contexts/linker helpers, host clocks, Tokio timers, ambient imports,
stdio, and native fallback are forbidden.

The exact logical-time state machine, public twelve-call probe, transcript hash
chain, three-fresh-instance equality rule, resource bounds, fail-closed results,
outer-supervisor authority, rollback-lesson interlock, and human-audit boundary
are frozen in the machine-readable fixture. They are specifications, not
executed evidence.

The `wall_clock_read = deny` canary remains frozen and unsatisfied. The checker
is not acceptance authority; an independent out-of-band commit/tree/checker/all-
path hash manifest is still required. Until that pin verifies, this result has
No authority.

The only permitted successor is the separate, public-static, no-run
`G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW`. No
component source/build/run, candidate/private/capability access, dependency or
runtime promotion, deployment, canary change, or G1.4 execution is authorized.
