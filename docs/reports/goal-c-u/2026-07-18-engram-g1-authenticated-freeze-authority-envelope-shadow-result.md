# Engram G1 Authenticated Freeze-Authority Envelope Shadow Result

Date: 2026-07-18

Verdict:
`SYNTHETIC_FIVE_SIGNATURE_ENVELOPE_CONFORMANCE_VERIFIED_NO_AUTHORITY`

## Result

A default-off, private `ab-store` shadow now verifies five role-separated
Ed25519 signatures over one exact restricted-canonical synthetic envelope. It
uses only in-memory test anchors and manifest bytes. The real adapter remains
`PENDING_IMPLEMENTATION_PREREQUISITES`; no corpus freeze, G1.4 opening, or
runtime authority is representable.

The first independent pre-implementation review returned `REVISE`. Before
closeout, the implementation added a domain-separated commitment over the
complete five-role anchor set, required that commitment both inside the signed
frame and in independent expected bindings, recomputed the bounded synthetic
manifest bytes, renamed the canonicalization profile as an RFC
8785-compatible restricted subset, and expanded canonicalization, KAT,
re-signing, alias, and repeated-call tests.

## Exact identities

- predecessor commit:
  `632918db75f65030d3ac15bc991b51a9c938cba6`;
- predecessor contract SHA-256:
  `a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0`;
- predecessor validator SHA-256:
  `632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde`;
- predecessor checker SHA-256:
  `ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29`;
- shadow contract SHA-256:
  `066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7`;
- structural validator SHA-256:
  `57e0b30fb459c1ac3ec2d9a0eff9ee6673fbd704f2b94702d5a5ebc35df76fe0`;
- Rust shadow module SHA-256:
  `5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef`;
- checker SHA-256:
  `8f602104ad6e6b35af4fe4e681f02c8303f3cc98256d119a0216e58cde24e6d4`.

## Implemented synthetic checks

- project-specific RFC 8785-compatible ASCII/safe-integer canonical subset;
- exact closed signing frame and duplicate/noncanonical JSON rejection;
- five fixed, ordered, distinct role signatures using existing optional
  `ring` Ed25519 verification;
- compile-time role domains and framed role/key/epoch messages;
- independently expected complete anchor-set commitment;
- exact G1.3, preregistration, repository, scope, packet, manifest, version,
  nonce, sequence, and time metadata bindings;
- bounded in-memory synthetic manifest byte rehash and length check;
- revision-floor, revocation, quorum, anchor-substitution, re-signing,
  cross-binding, and digest-alias rejection; and
- redacted, non-serializable result with every authority field false.

## Verification

The dedicated checker passes. Ten Rust tests cover a valid synthetic quorum,
RFC 8032 known-answer verification, malformed and one-bit signature tampering,
role/key/domain/anchor substitution, every scalar payload field after
re-signing, unsigned mutation, all five ordered packet digests, trust revision
and revocation, public/private digest aliases, root and nested duplicate JSON,
canonical byte/number/escape/UTF-8 bounds, manifest-byte mismatch, and repeated
verification without freshness or single-use claims.

The public contract validator deterministically emits a zero-authority receipt
and rejects every registered leaf mutation below the raw-byte pin. Static scans
confirm no filesystem, environment, clock, process, database, network, MCP, or
runtime path in the Rust shadow. The module is private; the feature is off by
default; `ring` is absent when the feature is not selected. The predecessor
adapter-preregistration checker also passes.

Full adjacent G0 through G1.3 regression and final independent read-only review
are recorded separately at closeout.

## Non-claims

No real key, person, role, trust root, trust revision, private corpus, file
identity, mount, custody, repository, scope, clock, freshness, replay claim,
capability, or consumer process was authenticated. No data access, BioCortex
execution, retrieval mutation, live write, deployment, or runtime promotion
occurred.

## Next boundary

Only a separate threat-reviewed secure-custody retained-descriptor shadow is
opened. Real private inputs, real trust-root provisioning, durable replay,
capability minting, freeze authority, and G1.4 remain closed.
