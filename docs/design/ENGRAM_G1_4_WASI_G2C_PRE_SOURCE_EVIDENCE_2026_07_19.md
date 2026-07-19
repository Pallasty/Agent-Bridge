# Engram G1.4 WASI G2C pre-source evidence

Date: 2026-07-19

Gate: `G2C_PRE_SOURCE_EVIDENCE_COMPLETION_REVIEW`

Mode: public/static/no-source/no-build/no-run

## Decision

G2C closes `B0_PRE_SOURCE` as an evidence barrier. It does not authorize the
next action. The resulting state is
`PRE_SOURCE_EVIDENCE_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION` and the
only successor is the separate
`G2D_PUBLIC_SOURCE_AUTHORIZATION_DECISION`.

No authority exists to author component, custom-host, or custom-WIT source;
install, promote, or compile dependencies; build or run a component; access
candidate/private/capability material; alter runtime, store, MCP, policy, or
deployment; open a canary or G1.4; or use a native/QEMU fallback. A green B0
is evidence for an owner decision, never implied authority.

## B0 evidence closed

1. The complete official `wasmtime-v46.0.1-src.tar.gz` payload is checked by
   exact size and SHA-256 against the immutable release pin. The three G2A
   crate payload digests remain pinned. The archive was not extracted or
   executed.
2. The exact minimal feature graph, 115-package lock, 114 registry checksums,
   Rust 1.94.0 toolchain payload digests, and host/guest target pins are
   inherited unchanged from G2A.
3. RustSec advisory-db commit
   `b5fc89b8be99e96f79194d8a6f11e9b4143b99f0` is rescanned by a checked-in,
   standard-library-only fail-closed scanner. It evaluates all 60 package
   version/advisory pairs represented by 59 unique advisory files and reports
   zero parse errors, vulnerabilities, and informational findings. This is an
   accepted-equivalent static receipt, explicitly not an official
   `cargo-audit` execution or receipt.
4. Wasmtime tag `v46.0.1` statically exposes
   `wasmtime::component::bindgen!`, `wasi:clocks@0.2.12`, and
   `wasi:io@0.2.12`. The exact future world contains only wall-clock,
   monotonic-clock, and poll. This closes B0 static compatibility; compiled
   compatibility remains a B2 obligation.
5. The host design fixes one logical-clock authority and direct exact-world
   implementations for wall-clock, monotonic-clock, deadline subscription,
   and poll readiness. Broad WASI linkers, Tokio time/sleep/instant, ambient
   host-clock fallback, and native/QEMU fallback are forbidden. This closes
   design-level B0 only; source proof remains B1 and built-linker proof B2.

## Reproduction and failure behavior

The checked-in checker validates receipt hashes, exact pins, claim boundaries,
deterministic summary output, path surface, and directed semantic mutations.
It also proves the RustSec instrument can detect a synthetic known-vulnerable
version and fail closed on unsupported requirement grammar.
An independent reviewer may additionally provide the complete release archive
and the pinned RustSec checkout to reproduce their byte-level results:

```bash
scripts/check-engram-g14-wasi-g2c-pre-source-evidence.sh \
  --phase precommit \
  --release-archive /path/to/wasmtime-v46.0.1-src.tar.gz \
  --rustsec-db /path/to/advisory-db
```

Any missing, changed, unknown, stale, or overclaimed evidence fails closed and
prevents transition. Source authorization, if any, must be an explicit owner
decision at G2D; source authorization still would not authorize build or run.

## Acceptance boundary

The checker is not self-authenticating. Acceptance requires an independent
clean-tree review plus an out-of-band feature commit, tree, checker digest, and
all-path hash manifest. No authority exists before both verified evidence and
the separate owner source authorization decision.
