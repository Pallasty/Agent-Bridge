# Agent Authority Signed Trust Root S3

Date: 2026-07-16

Status: DESIGN_FROZEN / OFFLINE_ED25519_PREFLIGHT / READ_ONLY_REPLAY_SNAPSHOT / NO_RUNTIME_AUTHORITY

## Decision

S3 replaces the S2 synthetic-attestation equality check with verification of
canonical Ed25519-signed authority receipts against a separate public trust
registry. It also evaluates key and receipt revocation, key and receipt
validity, nonce replay, current context, and a pure T6 review-evidence preview.

The verifier is an example/test artifact. The bridge production binary does not
consume receipts or gain authority.

## What S3 Advances

S2 proved deterministic binding between an evaluator-owned synthetic record and
an Agent-presented envelope. S3 proves a stronger offline property: the Agent
cannot modify any signed claim without invalidating a signature verified by a
public key selected from the evaluator trust registry.

S3 still assumes the registry fixture itself is trusted. It does not solve how
a production registry is distributed, protected, rotated, revoked, recovered,
or tied to a real owner identity.

## Source Lineage

- latest master:
  c9c50917687c7715b031a6bfe8dd7801bfd737ee
- S2 result:
  cdd426b846ff6c29bf008eba62a2d7bd57d09d4f
- S3 lineage merge:
  c0267f617d1636e688cc3d6e12f326191574c198
- S2 design SHA-256:
  5c34109bb215b017549f5012a0352f31b86d01f3d3cadbfcc7d5f62cc850a266
- S2 fixture SHA-256:
  a51b545d91fceecf81ec03d5355a686e0728b6ab92130b9cfc75b9a1983cd82c
- S2 result SHA-256:
  f56ee48902ffe60ce9a432c898a8d796ac3b998621b12483f3114d2c81fac31f

## Separated Fixtures

The evaluator-owned trust registry is:

    crates/bridge/tests/fixtures/agent_authority_trust_registry_s3.json

Its SHA-256 is:

    1e26edf7a5c71ac972d5c1c7e2496d8c1baa772d9571db995cfac04fe6c3d573

The Agent-presented signed-receipt corpus is:

    crates/bridge/tests/fixtures/agent_authority_signed_receipts_s3.json

Its SHA-256 is:

    1a15620e6dc16166d71b4458d5207eacf30579b8f631c48f85ac62fba2456d8d

The registry carries only public keys and read-only replay/revocation snapshot
data. The receipt corpus carries claims, signatures, availability input, and
expected comparison labels.

## Test Key Provenance

All registry entries use the Ed25519 public key from RFC 8032 section 7.1 test
vector 1. Fixture signatures were precomputed with OpenSSL 3.5.5 using the
corresponding published test seed.

The seed is public test data, not a production credential. It is not committed
to either fixture or embedded in the verifier. The verifier contains no signing
operation and uses ring 0.17.14 only for Ed25519 verification.

The ring dependency is dev-only for the bridge crate. It does not add a direct
dependency to the production agent-bridge binary target.

## Signed Claims

The signature binds 22 fields:

1. claims schema;
2. envelope version;
3. receipt id;
4. issuer id;
5. principal id;
6. action class;
7. target digest;
8. scope digest;
9. decision-source digest;
10. session-epoch digest;
11. resume-parent digest;
12. adapter id;
13. adapter-build digest;
14. adapter-capabilities digest;
15. issuance time;
16. expiry time;
17. nonce;
18. evidence digest;
19. verifier id;
20. policy version;
21. key id;
22. algorithm.

Canonical bytes use the domain:

    agent_bridge.authority_signed_receipt.s3.claims.v0

The domain is length-prefixed. Each field name is u16-length-prefixed. Strings
use a distinct type tag and u32 byte length; timestamps use a distinct type tag
and big-endian u64. Fields are emitted in the fixed order above.

The verifier checks the signature over canonical bytes directly. An
Agent-supplied digest is never a verifier input.

## Trust Registry

Each public key record binds:

- key id and algorithm;
- public key bytes;
- allowed issuer and principal;
- allowed action class and policy version;
- key not-before and not-after timestamps;
- revocation state.

The registry also contains a read-only snapshot of consumed nonces and revoked
receipt ids. The checker never appends to or mutates this snapshot.

Six fixture records model a primary active key, a same-owner key for the
out-of-scope action case, revoked and time-invalid keys, and an active key whose
issuer/principal/action/policy bindings differ.

## Frozen-Fixture Erratum

The first RED-to-GREEN run exposed a contradiction in `wrong_action_rejected`:
the receipt used the primary key while changing the action to `memory_write`,
so the frozen key-binding-first pipeline correctly derived `untrusted` before
the case could exercise current-context scope rejection.

Before any passing result, registry version `2026-07-16.2` added a public-test
key bound to the same issuer, principal, and policy but to `memory_write`. The
case now selects that key and carries a fresh public-test signature. No expected
state, state count, pipeline order, or authority boundary changed; only the
fixture precondition needed to make the preregistered scope case reachable was
corrected. The hashes above identify the corrected freeze.

## Verification Pipeline

The pipeline is dependency-aware and fail-closed:

1. Reject unavailable verification as unavailable.
2. Reject malformed receipt structure, Base64, signature length, claims schema,
   envelope version, verifier id, time ordering, or digest shape as invalid.
3. Reject unknown key ids, disallowed algorithms, key/algorithm mismatch, or
   issuer/principal/action/policy key-binding mismatch as untrusted.
4. Verify Ed25519 over canonical bytes with ring; failure is invalid.
5. Reject valid signatures from revoked keys or revoked receipt ids as revoked.
6. Reject time-invalid keys or receipts, including receipt issuance outside
   key validity, as stale using the frozen skew rule.
7. Reject consumed nonces as replayed.
8. Reject action, target, scope, decision source, session, resume, adapter, or
   evidence mismatch as out_of_scope.
9. Otherwise derive verified.

Expected status and expected reasons are comparison data consulted only after
derivation. Reasons are emitted in lexical order.

## Frozen Distribution

| State | Count |
|---|---:|
| verified | 4 |
| invalid | 4 |
| untrusted | 3 |
| revoked | 2 |
| stale | 4 |
| replayed | 1 |
| out_of_scope | 8 |
| unavailable | 1 |
| total | 27 |

The four controls include exact receipt clock-skew boundaries. Adversarial
cases cover malformed, short, bit-flipped, and payload-mismatched signatures;
unknown key, algorithm confusion, trust-binding mismatch; key/receipt
revocation and validity; nonce replay; all S2 context bindings; and verifier
unavailability.

## T6 Consumption Preview

A verified result may set receipt_usable_for_later_owner_review to true. This
means only that a later human review may cite the receipt.

Every report keeps these false:

- may_dispatch;
- may_run_shadow;
- may_enable_runtime;
- may_write_memory;
- may_write_graph;
- may_change_retrieval;
- may_change_session;
- may_persist_replay_state;
- production_trust_root_proven;
- production_authority_granted.

No T6 function, MCP tool, runtime gate, or storage transaction consumes this
result.

## Acceptance

- both fixture hashes and all source pins match;
- 27 unique cases derive the frozen distribution;
- zero false accepts and zero control false rejects;
- exact status and reasons for every case;
- every signed field changes canonical bytes;
- malformed or ambiguous registry mutations fail closed;
- signatures are verified by ring, not custom cryptography;
- repeated reports are byte-identical;
- all authority fields remain false.

## Deferred Work

S3 does not provide production key custody, hardware-backed identity, registry
distribution, threshold authorization, online status checks, durable atomic
nonce consumption, audit-log persistence, T6/MCP integration, runtime
admission, deployment, or a production-security claim.
