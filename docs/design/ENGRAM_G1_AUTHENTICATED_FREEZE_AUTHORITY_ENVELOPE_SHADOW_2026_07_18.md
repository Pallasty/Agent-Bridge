# Engram G1 Authenticated Freeze-Authority Envelope Shadow

Date: 2026-07-18

Status: **SYNTHETIC OFFLINE SHADOW IMPLEMENTED / REAL ADAPTER PREREQUISITES PENDING / NO AUTHORITY**

## Decision

This gate implements only a private, synthetic, offline five-signature
envelope-conformance shadow. A successful result means that five test-only
Ed25519 signatures validate against an explicitly caller-supplied synthetic
anchor set and that the exact restricted-canonical signed payload equals
caller-pinned synthetic expectations.

It does not authenticate real people, roles, evidence, repository identity,
scope custody, manifest custody, trust-root provisioning, key currentness,
freshness, sequence currentness, replay protection, or capability consumption.
The real adapter remains `PENDING_IMPLEMENTATION_PREREQUISITES`. This is not a
corpus freeze, not authenticated freeze authority, and not G1.4.

The registered public contract is
`scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_envelope_shadow_contract_v0.json`,
SHA-256
`066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7`.
Its public structural validator SHA-256 is
`57e0b30fb459c1ac3ec2d9a0eff9ee6673fbd704f2b94702d5a5ebc35df76fe0`.
The private Rust shadow module SHA-256 is
`5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef`.
The checker SHA-256 is
`8f602104ad6e6b35af4fe4e681f02c8303f3cc98256d119a0216e58cde24e6d4`.

The gate pins predecessor commit
`632918db75f65030d3ac15bc991b51a9c938cba6` and the exact preregistration
contract, validator, and checker digests. That predecessor is design-only and
grants no authority.

## Reachability boundary

The implementation lives in the private crate-root module
`crates/store/src/engram_g1_authenticated_envelope_shadow.rs` behind Cargo
feature `engram-g1-authenticated-envelope-shadow-synthetic`.

- The feature is disabled by default and activates only the already-present
  optional `ring` dependency.
- The module is declared with private `mod`, has no `pub use`, and has no
  bridge, binary, MCP, runtime, or production caller.
- Signing seeds and `Ed25519KeyPair` exist only under `#[cfg(test)]`.
- Non-test code verifies only; it cannot load a private key.
- The module performs no filesystem, environment, clock, process, SQLite,
  network, store, or write operation.
- Its result is private, non-serializable, redacted, and marked `must_use`.

Enabling the feature makes synthetic unit tests buildable. It does not enable
an adapter or runtime path.

## Four independent synthetic inputs

Verification accepts four in-memory inputs:

1. exact canonical synthetic envelope bytes;
2. a typed five-anchor synthetic ledger supplied outside the envelope;
3. caller-pinned expected bindings; and
4. bounded synthetic manifest bytes.

The verifier recomputes the synthetic manifest digest and byte length. This
closes digest-only test-vector ambiguity, but it proves neither file identity
nor custody: no real file is opened and no retained descriptor exists.

## Restricted canonicalization profile

The canonicalization profile accepts only a project-specific RFC
8785-compatible subset:

- compact UTF-8 JSON with no BOM, whitespace, or trailing bytes;
- 7-bit ASCII object keys and string values;
- nonnegative integers from 0 through `9007199254740991`;
- recursively sorted keys; and
- no duplicate keys, floats, negative numbers, exponent spellings,
  noncanonical escapes, unknown fields, or noncanonical bytes.

It is not a general RFC 8785 implementation. Values outside the subset are
rejected rather than normalized. The implementation also caps the envelope at
64 KiB, nesting at 16, strings at 4096 bytes, keys at 128 bytes, and arrays or
objects at 64 members.

## Signed object and quorum

The exact signing frame contains the schema, envelope kind, canonicalization
profile, message profile, and every semantic payload field. The `signatures`
array is excluded to avoid circular signing.

Each role signs an unambiguous length-framed message containing:

- the frozen message profile;
- its compile-time role domain;
- its role, key identifier, and key epoch; and
- the exact canonical signing frame bytes.

The five compile-time roles remain, in order:

1. application owner;
2. independence auditor;
3. freeze reviewer 1;
4. freeze reviewer 2; and
5. sealed evaluator custodian.

Roles, key identifiers, public keys, and synthetic signer-identity commitments
must all be pairwise distinct. The envelope cannot carry a public key or trust
anchor. A domain-separated anchor-set commitment binds all five roles, key
identifiers, epochs, public keys, identity commitments, repository, scope, and
synthetic ledger revision. That commitment is inside the signing frame and
must independently match the caller-pinned expected binding, so all five
signatures bind the whole signer set rather than only their own slots.

The in-memory revision floor and revocation fields test fail-closed logic only.
They do not provide durable rollback protection, provisioning independence, or
claim-time currentness.

## Exact synthetic bindings

The signing frame binds:

- hardened G1.3 commit, contract, validator, and checker identities;
- adapter-preregistration commit, contract, validator, and checker identities;
- five ordered synthetic G1.3 packet digests;
- recomputed synthetic manifest digest and byte length;
- repository and scope identity commitments;
- the complete anchor-set commitment and synthetic ledger revision;
- adapter and implementation profiles;
- a 32-byte nonce, sequence, issue time, expiry, boot-epoch commitment, and
  signed-time-checkpoint commitment; and
- explicit false custody, trust, time, replay, capability, freeze, G1.4, and
  runtime fields.

Unsigned mutation fails the signatures. Mutation followed by re-signing still
fails the independent expected binding. Private packet and manifest digests
must be nonzero, pairwise disjoint, and disjoint from public predecessor,
contract, repository, scope, anchor-set, signing-message, signing-frame, and
envelope digests.

## Freshness and replay non-claims

Issue and expiry metadata are signed, calendar-independent integers with
`expiry > issue` and a maximum interval of 24 hours. The verifier does not read
a clock. It cannot establish the 15-minute claim window, current freshness,
sequence monotonicity, boot continuity, a durable high-water mark, or replay
consumption.

The same valid synthetic envelope may be verified twice and return the same
conformance result. Both results explicitly keep trusted time, durable replay,
single-use claim, and capability minting false. This behavior is a test of the
boundary, not an incomplete replay claim.

## Current zero-authority result

Only two synthetic conformance facts may be true:

- five test signatures conform to the frozen signature and expected-binding
  rules; and
- the supplied synthetic anchor set and manifest bytes match their independent
  commitments.

Every secure-custody, durable-trust, trusted-time, replay, capability,
freeze-authority, G1.4-readiness, live-write, mutation, execution, promotion,
and runtime-authority claim remains false. The result emits only the envelope
and signing-frame digests and does not expose keys, key identifiers, identity
commitments, packet or manifest digests, nonce, repository, or scope.

## Human-audit boundary

This default-off, synthetic, reversible shadow does not provision persistent
trust and does not require a manual transition audit. The preregistered manual
audit boundary remains unchanged for initial real trust-root provisioning,
key/role/quorum governance, scope or filesystem-policy widening, first
production enablement, and suspected secret, privacy, or identity exposure.

## Next admissible gate

The only next engineering action opened here is a separate synthetic or
disposable secure-custody retained-descriptor shadow gate. It must implement
component-by-component no-follow traversal, retained repository/parent/file
descriptors, regular-file and `st_nlink == 1` policy, owner-only modes, mount
identity, before/after `fstat`, and final name-to-inode revalidation.

That successor may not load a real private corpus, provision real trust roots,
mint a capability, or open G1.4 without its own threat review and the remaining
durable trust, trusted-time, replay-CAS, claim-time revocation, and capability
gates.

## Run

```bash
scripts/check-engram-g1-authenticated-freeze-authority-envelope-shadow.sh
```

The checker pins the contract, validator, and module bytes; recursively mutates
every public contract leaf; rejects duplicate, symlinked, and byte-drifted
contracts; scans for forbidden I/O/runtime surfaces; proves the feature is
private and default-off; runs ten focused Rust attack/KAT tests; confirms the
optional crypto dependency is unreachable when the feature is absent; and
runs the predecessor preregistration checker.
