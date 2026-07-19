# Engram G1.4 stronger clock-isolation primitive review result

Date: 2026-07-18

Verdict: **`DESIGN_ROUTE_SELECTED_NO_AUTHORITY`**.

## Selected design route

- Reject host-native nono/Seatbelt/Landlock/seccomp/time-namespace,
  interposition, syscall-supervision, and default hardware-VM paths as complete
  G1.4 host-clock boundaries.
- Carry `wasi_component_custom_clocks` as the primary public-synthetic
  feasibility candidate.
- Carry `qemu_tcg_icount_fixed_rtc` only as the native-binary compatibility
  fallback.
- Require `supervisor_owned_authoritative_time` as an overlay in either route;
  never count it as standalone candidate-visible clock isolation.

The current `wall_clock_read = deny` canary
`REMAINS_FROZEN_AND_UNSATISFIED`. A future proposal may replace API denial
with “no host clock plus supervisor-defined deterministic time,” but that
change cannot admit candidate/private/runtime work without human security
audit.

## Evidence result

The static review pinned ten primary-source claims, nine candidate rows, three
ordered future gates, predecessor file hashes, nono 0.53.0 metadata, and the
accepted negative KAT lineage. The checker rejects authority flips, source or
matrix reorder, host-native promotion, default-VM promotion, audit bypass,
candidate substitution, gate removal, predecessor drift, checker
self-authentication claims, out-of-band-pin bypass, and nonclaim flips.

The checker is not an acceptance authority and does not authenticate its own
same-commit source. Acceptance requires an independent read-only reviewer to
produce a manifest pinning its session and PASS verdict to the exact feature
commit, tree, semantic-checker SHA-256, and all seven feature-path SHA-256
values. The manifest must be published and verified out of band in the Agent-
Bridge forum. Before then, the result remains evidence only and carries no
authority.

No policy was compiled or applied. No native probe, WASI component, VM,
candidate, private artifact, or capability was launched or opened. No runtime,
crate, MCP, store, retrieval, or deployment path changed.
No deployment or reconnect is required.

## Next action

The only selected reversible successor is a separate
`G2_WASI_PREREGISTRATION` design gate. It must pin a public component ABI,
Wasmtime/dependency review, explicit custom wall and monotonic clocks, closed
imports, deterministic transcripts, and a supervisor-owned authority overlay.
It grants no execution authority by itself.

QEMU preregistration stays deferred until WASI compatibility is disproved or
materially insufficient. G1.4 remains closed.
