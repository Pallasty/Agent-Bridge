# Engram G1.4 G2 WASI custom-clock preregistration

Date: 2026-07-19

Status: **CANONICAL_WIT_CONTRACT_SELECTED_STATIC_ONLY; No authority**.

## Decision

The accepted stronger-clock review selected `wasi_component_custom_clocks` as
the primary route to investigate. This G2 contract makes that route precise
without adding a dependency, authoring or building a component, implementing a
clock, running a probe, or opening G1.4. The frozen `wall_clock_read = deny`
canary remains unchanged and unsatisfied.

The selected canonical WIT is
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, bound to
SHA-256 `d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be`.
It declares package `agent-bridge:g14-clock-probe@0.1.0` and world `probe` (the
fully qualified world is `agent-bridge:g14-clock-probe/probe@0.1.0`). Its
complete import allowlist is:

1. `wasi:clocks/wall-clock@0.2.12`;
2. `wasi:clocks/monotonic-clock@0.2.12`;
3. `wasi:io/poll@0.2.12`.

It has the sole export `typed-report: func() -> typed-report`. The result is the
`typed-report` record with fields, in order, `wall-epoch-seconds: u64`,
`logical-nanoseconds: u64`, and `quantum-nanoseconds: u64`. Stdout and stderr
are not report channels. The built component's import graph must equal the allowlist exactly;
an unknown or transitive runtime import closes the gate. CLI, filesystem,
network, HTTP, random, timezone, inherited descriptors, preopens, WASI P1, and
native-process fallback are absent and forbidden.

## Why replacing only `now()` is insufficient

The review target is Wasmtime `v46.0.1`, Git commit
`823d1b8f251494a06288194d0df746191f535ff7`, with its vendored
`wasi:clocks@0.2.12` and `wasi:io@0.2.12` definitions. The three crates.io rows
for `wasmtime`, `wasmtime-wasi`, and `wasmtime-wasi-io` are checksum-pinned in
the fixture. These are public review targets, not adopted Cargo dependencies.

The decisive source finding is narrower than the public `WasiCtxBuilder` API
suggests. `HostMonotonicClock` replaces `now` and `resolution`, but Wasmtime's
built-in Preview 2 `subscribe-instant` and `subscribe-duration` host methods use
Tokio `Instant::now()` and `sleep_until()`. A custom `HostMonotonicClock` alone
therefore does not close the host-elapsed-time channel. Likewise, the top-level
Preview 2 `add_to_linker` helpers install a broad WASI surface.

The future harness must consequently use bindings generated for the exact
probe world and directly implement all three host interfaces: wall clock,
monotonic clock including both subscription methods, and I/O poll. It may not
construct a broad `WasiCtx`, use `WasiCtxBuilder`, call top-level/proxy
`add_to_linker` helpers, or reuse Wasmtime's built-in monotonic subscription
host. All three interfaces share one logical-clock state. Tokio time and every
ambient host clock or sleep path are forbidden.

The locked upstream source rows and SHA-256 values are in
`scripts/eval/fixtures/engram_g14_wasi_clock_preregistration_v0.json`, including
Wasmtime's context defaults, clock traits, linker surface, timer host, and
vendored clock/poll WIT. They establish what was reviewed; they do not prove a
future binary or dependency graph safe.

## Deterministic time semantics

The logical clock starts at `0 ns`, has a `1,000,000 ns` quantum, and maps wall
time to the fixed public epoch `2000-01-01T00:00:00Z` (`946684800` seconds).
Both resolutions are exactly one quantum and do not advance time.

- `wall-clock.now` returns epoch plus the current logical value, then advances
  one quantum using checked `u64` arithmetic.
- `monotonic-clock.now` returns the current logical value, then advances one
  quantum.
- `subscribe-duration(d)` registers `current + d`; `subscribe-instant(t)`
  registers `t`. Neither advances time.
- `poll` accepts a non-empty list containing only registered timer pollables.
  If any deadline is already ready, it returns every ready input index in caller
  order without advancing. Otherwise it jumps logical time directly to the
  minimum deadline and then returns every ready input index in caller order.
- Pollable IDs are monotonic creation-order integers. Empty, foreign, mixed, or
  over-limit pollables and arithmetic overflow trap with no receipt.

The fixture freezes a twelve-call public sequence that covers resolution, both
`now` methods, duration and instant subscriptions, immediate readiness, a
logical jump, and a zero-duration timer. Its final logical value is
`7,000,000 ns`. No call reads or waits for host time.

Every call produces a canonical integer/string-only JSON event containing its
sequence, operation, arguments, result, and logical time before and after. A
domain-separated SHA-256 chain binds the event bytes and lengths. A future
feasibility gate must use three fresh stores/instances and prove byte equality
for component digest, import/export manifest, typed report, transcript, and
chain root. Candidate-visible time can never supply protocol timestamps,
freshness, ordering, expiry, or replay authority; those remain exclusively with
the outer supervisor.

## Bounds and fail-closed behavior

The future public probe is capped at 256 KiB of component bytes, 16 MiB linear
memory, 1,024 table elements, 8 instances, 64 clock events, 16 live pollables,
16 KiB of typed report, and 2,000,000 fuel. A five-second outer supervisor
timeout may use trusted supervisor time but is not visible to the component.
Timeout, trap, exhaustion, drift, or oversized output produces no feasibility
receipt.

## Supply-chain and audit interlock

This change downloads nothing into the repository and adds no Cargo metadata.
No advisory verdict is claimed. Before component source, build, or execution,
a separate static G2A review must verify release and crate payload digests, the
minimal feature graph, a complete lockfile and transitive checksums, exact
toolchain and targets, a timestamped RustSec database commit and raw audit
receipt hash, WIT/bindgen compatibility, and source-level proof that direct
clock/poll bindings bypass every built-in host timer path. It must also pre-pin
the future public component, import manifest, and custom host source digests.
Missing or drifted evidence is `FAIL_CLOSED_NO_SOURCE_NO_BUILD_NO_RUN`.

The user's reversible-work policy is explicit: neither this static gate nor a
separately authorized isolated public-synthetic experiment needs human
approval. Independent read-only review remains mandatory. A human security
audit is required before promoting a Wasmtime/WASI dependency into the
Agent-Bridge runtime, changing the frozen canary outside a public-synthetic
harness, touching candidate/private/capability material, enabling runtime or
deployment behavior, or performing the first real G1.4 run.

If rollback or cleanup fails, retry is blocked until a create-new durable lesson
is fsynced, reopened, and hash-verified. Failure to persist that lesson leaves
an absorbing interlock.

## Verification and successor

Run the semantic checker before and after the isolated feature commit:

```bash
scripts/check-engram-g14-wasi-clock-preregistration.sh --phase precommit
scripts/check-engram-g14-wasi-clock-preregistration.sh --phase postcommit
```

The checker rejects authority flips, broad linker/context use, built-in host
timers, import drift, altered time/poll semantics, weaker evidence or audit
interlocks, and changed bounds. Its mutation tests call the semantic validator
directly, separately from raw-byte pins. The checker is not self-authenticating.
Acceptance additionally requires an independent forum manifest binding the
reviewer session, PASS verdict, feature commit and tree, checker SHA-256, and
SHA-256 of every one of the exact seven feature paths.

The only permitted successor is
`G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW`. It is a
separate public, static, no-run gate. This preregistration authorizes neither
that review's successor nor component source/build/run, candidate/private
access, dependency promotion, deployment, canary change, or G1.4 execution.

## Nonclaims

No host clock or timer isolation has been verified. No dependency/advisory
review is complete. No bindings have been generated, no component ABI SHA has
been observed, and no component ABI has been compiled or import graph observed.
No dependency/WIT generation, component, linker, build, run, runtime, or deploy
work is authorized. No custom host exists. No public probe, candidate, private
input, runtime, deployment, or G1.4 authority is present.
