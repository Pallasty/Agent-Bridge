# Engram G1.4 G2A public WASI artifact and compatibility review

Date: 2026-07-19

Status: **public static evidence review; fail closed; No authority**.

## Decision

G2A does not authorize component or host source, a build, a run, dependency
promotion, candidate/private access, deployment, canary change, or G1.4. It
audits the nine ordered requirements frozen by G2 and records the reproducible
public evidence that can be obtained without crossing those boundaries.

Verdict:
`G2A_FAIL_CLOSED_UNSATISFIABLE_ARTIFACT_ORDER_NO_SOURCE_NO_BUILD_NO_RUN`.

The blocker is causal, not merely an absent download. G2 requires all nine
items **before any component source, build, or run**, but three items can only
exist after actions G2 forbids:

1. a fixed component-source digest requires component source to exist;
2. a fixed component binary and observed import-manifest digest require a
   component build (or an already accepted matching public binary);
3. a custom clock/poll host-source digest requires host source to exist.

Wasmtime v46.0.1 is an immutable GitHub release with 38 assets. Its published
asset inventory contains runtimes, C API archives, three Preview 1 adapters,
headers, and the source archive; it contains no G1.4/custom-clock component.
Consequently no official prebuilt artifact closes the causal gap.

## Evidence closed without source or build

The three reviewed crates.io payloads were downloaded independently and match
the G2 pins exactly: `wasmtime`, `wasmtime-wasi`, and `wasmtime-wasi-io`
46.0.1. A resolver-only manifest using `wasmtime` with default features off and
only `component-model`, `cranelift`, `runtime`, and `std` produced the checked-in
evidence lockfile. It contains 115 package stanzas (the local resolver plus 114
dependencies), and every registry package has a checksum. The resolved graph
does not contain `wasmtime-wasi`, `wasmtime-wasi-io`, Tokio, `cap-time-ext`, or
`system-interface`.

The resolver stub is evidence only: it was neither compiled nor promoted into
Agent-Bridge. The lockfile's raw SHA-256 and expected root/features are pinned
in the machine-readable contract.

Rust 1.94.0 is pinned by the official channel manifest and its SHA-256, with
`aarch64-apple-darwin` as the host target and `wasm32-wasip2` as the future
guest target. The guest target was not installed. The official host toolchain,
host standard library, guest standard library, rustc, and Cargo payload hashes
are recorded as public review pins, not installed artifacts.

RustSec advisory-db commit
`b5fc89b8be99e96f79194d8a6f11e9b4143b99f0` is pinned. A bounded static scan
matched the exact lock package names and versions against 59 non-withdrawn
advisory files and found zero vulnerabilities with zero parse errors. Its raw
receipt is checked in and hashed. `cargo-audit` was not installed or executed,
so the advisory requirement remains partial and must be repeated with an
official or separately accepted equivalent scanner before dependency promotion.
Yanked status is likewise explicitly unreviewed rather than silently claimed.

## Compatibility evidence that remains conditional

Wasmtime's public source confirms that `component::bindgen!` generates direct
host traits for an exact WIT world. The G2 world allows exactly
`wasi:clocks/wall-clock@0.2.12`,
`wasi:clocks/monotonic-clock@0.2.12`, and
`wasi:io/poll@0.2.12`. Source inspection also confirms why the broad
`wasmtime-wasi` host is forbidden: its clock subscriptions create Tokio
instants, call Tokio sleep/yield paths, and its broad linkers install unrelated
WASI interfaces.

The minimal resolved graph shows that an exact-world host can avoid importing
that broad implementation as a dependency. This is architecture evidence, not
compiled ABI evidence. Until exact host source exists, no checker can prove its
generated trait implementations, linker calls, or import graph actually bypass
all built-in timer paths. G2A therefore marks WIT/bindgen compatibility partial
and timer-path bypass conditional.

## Why the source archive is not overclaimed

The immutable GitHub release API publishes the source archive's size and
SHA-256. G2A records that official digest but does not claim an independent
local byte match of the full 152,108,252-byte archive. This alone would keep the
first requirement partial even without the stronger causal blocker.

## Required ordering repair

The only permitted successor is the separate public-static, no-run
`G2B_PUBLIC_WASI_ARTIFACT_ORDERING_REPAIR_PREREGISTRATION`. It may amend only
the ordering defect by freezing three explicit barriers:

1. before source authoring: release/crate, dependency, lockfile, toolchain,
   advisory, exact-world, and static timer-path design evidence;
2. after separately authorized public source authoring but before build: exact
   component and host source digests;
3. after separately authorized public build but before run: exact component
   binary and observed import/export-manifest digests.

G2B itself authorizes none of those later actions. Missing evidence at any
barrier remains fail closed. No silent native/QEMU fallback is introduced.

## Verification

Run the semantic checker before and after the isolated feature commit:

```bash
scripts/check-engram-g14-wasi-g2a-artifact-compatibility.sh --phase precommit
scripts/check-engram-g14-wasi-g2a-artifact-compatibility.sh --phase postcommit
```

The checker validates the predecessor order, evidence states, raw evidence
lockfile, fail-closed verdict, authority locks, and unique successor. Its
mutation tests invoke semantic validation independently of raw-byte pins. A
passing checker is not acceptance authority; independent read-only review and
an out-of-band commit/tree/checker/all-path hash manifest remain required.

## Nonclaims

No source archive byte match, yanked-package review, compiled WIT binding,
observed component import graph, custom host, component source, component
binary, build, run, dependency adoption, candidate/private access, deployment,
canary change, timer isolation, or G1.4 authority is claimed.
