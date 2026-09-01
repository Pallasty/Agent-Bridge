# Invocation Guardian v2 C0 source result

Date: 2026-09-01

Status: **C0 PASS; C1—C4 and production remain HOLD**

## Decision

The repository now has one canonical, self-contained signed canary lease scope
and an independently framed v2 guardian protocol. This is a source-level schema
and downgrade boundary only. It grants no production authority and registers no
effect.

## Implemented

- `crates/bridge/src/invocation_lease_scope.rs`
  - bounded canonical encoding and strict canonical decode;
  - Ed25519 domain-separated signing and verification;
  - externally pinned key generation, verify-key commitment, ledger generation,
    and namespace;
  - exact binding to tool, JCS arguments digest, target, finalized registry,
    principal, stdio transport, server-owned connection commitment, validity
    window, and `max_uses=1`;
  - a 60-second maximum canary TTL.
- `crates/bridge/src/invocation_guardian_protocol_v2.rs`
  - independent `ABI2` magic/version and a 4096-byte frame ceiling;
  - canonical consume request carrying observed invocation material plus the
    signed envelope;
  - closed outcomes where only `FreshCommitted` can report a live dispatch
    grant;
  - separate receipt disposition binding so outcome-bit flipping is rejected;
  - `AlreadyCommitted` may retain an audit receipt but never grants dispatch.

## Verification

All commands used an isolated target directory at
`/var/tmp/agent-bridge-c0-target`.

```text
cargo test -p ab-bridge --lib invocation_lease_scope --no-default-features
3 passed / 0 failed

cargo test -p ab-bridge --lib invocation_guardian_protocol_v2 --no-default-features
4 passed / 0 failed

cargo check -p ab-bridge --no-default-features
PASS
```

The protocol tests cover canonical round trips, v1/v2 cross-decode rejection,
unknown tags, reserved-bit mutation, truncation, oversize, non-fresh authority
rejection, and outcome/receipt-disposition flipping. Scope tests cover wrong
keys, pin mismatch, time bounds, noncanonical bytes, and every observed
invocation binding.

Existing repository warnings remained present; no new compile error or warning
was attributed to these modules.

## Boundaries and next gate

- no guardian v2 client or non-clone permit;
- no async protected witness trait or provider receipt verifier;
- no canary profile, MCP `tools/call` E2E, marker sink, or fault injection;
- no deployment identity, IPC, anti-rollback provider, key, namespace, or state;
- no production build, publication, service restart, or deployment;
- v1 remains permanently `volatile_lab` and non-authoritative;
- ordinary `AB_INVOCATION_LEASE_MODE=enforce` remains Invalid/HOLD.

The next admissible goal is C1: a default-off source canary using an async fake
witness, a non-clone fresh-only permit, fixed marker sink, fault matrix, and a
real stdio child-process `tools/call` E2E. Protected-witness and deployment
claims remain gated by C2 and C3 external evidence.
