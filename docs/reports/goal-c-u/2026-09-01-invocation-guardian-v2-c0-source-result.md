# Invocation Guardian v2 C0 source result

Date: 2026-09-01

Status: **C0 PASS; C1—C4 and production remain HOLD**

## Decision

The latest `origin/master` integration baseline now has one canonical,
self-contained signed canary lease scope, one canonical signed provider receipt,
and an independently framed v2 guardian protocol. This is a source-level schema,
receipt-verification, and downgrade boundary only. It grants no production
authority and registers no effect.

## Implemented

- `crates/bridge/src/invocation_lease_scope.rs`
  - bounded canonical encoding and strict canonical decode;
  - Ed25519 domain-separated signing and verification;
  - externally pinned key generation, verify-key commitment, ledger generation,
    and namespace;
  - fixed canary lane, tool, principal kind, stdio transport and server-created
    connection-context kind;
  - exact binding to JCS arguments digest, target, finalized registry,
    principal commitment, server-owned connection commitment, positive validity
    window, and `max_uses=1`;
  - a 60-second maximum canary TTL with exclusive expiry.
- `crates/bridge/src/invocation_guardian_receipt_v2.rs`
  - bounded canonical receipt encoding and domain-separated Ed25519 signature;
  - external pins for provider verify key/generation, provider identity,
    namespace, and minimum epoch/revision;
  - exact binding to previous/new head, token, `use_index=1`, exact scope,
    current request challenge, guardian session, provider time and disposition;
  - verified evidence is non-`Clone` and is explicitly not a dispatch permit.
- `crates/bridge/src/invocation_guardian_protocol_v2.rs`
  - independent `ABI2` magic/version and a 4096-byte frame ceiling;
  - canonical consume request carrying observed invocation material plus the
    signed envelope;
  - complete closed outcomes including lookup, exhausted and revoked states;
  - typed signed receipts with outcome/disposition, request, session and exact
    scope consistency checks;
  - raw decode has no grant/dispatch predicate; signature and pin verification
    are mandatory before producing verified evidence;
  - `AlreadyCommitted` may retain verified audit evidence but never becomes a
    permit.

## Verification

Commands ran in the isolated current-integration worktree with `-j1`.

```text
cargo test -p ab-bridge --lib invocation_lease_scope --no-default-features
4 passed / 0 failed

cargo test -p ab-bridge --lib invocation_guardian_receipt_v2 --no-default-features
3 passed / 0 failed

cargo test -p ab-bridge --lib invocation_guardian_protocol_v2 --no-default-features
4 passed / 0 failed

cargo check -p ab-bridge --no-default-features
PASS
```

The protocol tests cover canonical round trips, v1/v2 cross-decode rejection,
unknown tags, reserved-bit mutation, truncation, oversize, forged signatures,
old request challenges, all denied outcomes, and outcome/receipt-disposition
flipping. Scope and receipt tests freeze golden canonical digests and cover
wrong keys, pin mismatch, exclusive time bounds, stale provider position,
noncanonical bytes, and every signed or observed binding.

Existing repository warnings remained present; no new compile error or warning
was attributed to these modules.

## Boundaries and next gate

- no guardian v2 client or non-clone permit;
- no async protected witness trait or protected provider implementation;
- no canary profile, MCP `tools/call` E2E, marker sink, or fault injection;
- no deployment identity, IPC, anti-rollback provider, key, namespace, or state;
- no production build, publication, service restart, or deployment;
- v1 remains permanently `volatile_lab` and non-authoritative;
- ordinary `AB_INVOCATION_LEASE_MODE=enforce` remains Invalid/HOLD.

The next admissible goal is C1: a default-off source canary using an async fake
witness, a non-clone fresh-only permit, fixed marker sink, fault matrix, and a
real stdio child-process `tools/call` E2E. Protected-witness and deployment
claims remain gated by C2 and C3 external evidence.
