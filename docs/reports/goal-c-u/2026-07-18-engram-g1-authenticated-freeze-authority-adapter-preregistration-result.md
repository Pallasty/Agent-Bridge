# Engram G1 Authenticated Freeze-Authority Adapter Preregistration Result

Date: 2026-07-18

Verdict:
`AUTHENTICATED_FREEZE_AUTHORITY_ADAPTER_PREREGISTERED_DESIGN_ONLY_FAIL_CLOSED`

## Result

The design contract for a future G1 authenticated freeze-authority adapter is
now fixed and structurally validated. No adapter, cryptographic verifier,
trust-root ledger, secure-custody reader, replay ledger, capability minter,
private evidence, key material, or runtime path was introduced.

Current state remains `PENDING_IMPLEMENTATION_PREREQUISITES`. A positive
authority state is not representable, and G1.4 remains closed.

## Exact bindings

- predecessor commit:
  `7062869196d1a3ff8bb72572a39700e65130cde4`;
- predecessor G1.3 contract SHA-256:
  `5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504`;
- predecessor G1.3 validator SHA-256:
  `0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089`;
- predecessor G1.3 checker SHA-256:
  `e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39`;
- preregistration contract SHA-256:
  `a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0`;
- preregistration validator SHA-256:
  `632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde`;
- preregistration checker SHA-256:
  `ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29`.

The checker digest is an external review/Git-tree identity. The executable
checker pins the contract and validator; it does not claim to self-pin its own
digest, which would require a circular hash fixed point.

## Frozen controls

The future implementation must provide:

- five distinct, domain-separated Ed25519 role signatures against an
  independently provisioned private capability-control ledger;
- component-by-component no-follow path traversal with retained repository,
  parent, and file descriptors;
- regular-file, `st_nlink == 1`, owner-only mode, same-local-filesystem, and
  final name-to-inode checks;
- exact G1.3 packet, manifest, repository, scope, adapter-version, key-epoch,
  nonce, sequence, freshness, and expiry binding;
- RFC 8785 canonical signed bytes, monotonic time plus a durable boot epoch,
  signed time checkpoint, high-water mark, and append-only single-use CAS claim
  ledger; and
- one consumer-key/process-bound, non-bearer typed capability whose only
  possible successor is a separate G1.4 design review.

Every missing or inconsistent control rejects fail closed.

## Human-audit boundary

Routine reversible validation and unchanged authenticated checks require no
human approval. Fail-closed denial also does not create a human gate.
Reversible failure must roll back automatically; rollback failure must record
a durable lesson with residual-state evidence.

Manual safety audit is limited to initial trust-root provisioning, key
rotation/revocation, signer or quorum changes, repository/scope/predecessor
widening, filesystem/hardlink/mount policy changes, first production adapter
enablement, and suspected secret/privacy/identity exposure.

## Verification

The dedicated checker passed. It pins the current contract and validator
digests, verifies deterministic receipts and exact public predecessor
identities, and drives at least 90 semantic mutations below the public
raw-byte pin. Recursive exact validation covers every nested field, value,
array order/length, and JSON type. Duplicate JSON and symlink inputs reject.
The new validator plus its imported public reader have no crypto, network,
process, or database imports and expose no private-input or key CLI.

The checker deliberately proves that a hardlink of the public contract still
produces secure-custody and authority false. Hardlink rejection belongs to the
future private-file adapter and is not claimed by this structural gate.

All adjacent G0 through G1.3 gates passed. The first independent review found
that the initial mutation matrix stopped at the raw hash and that nested exact
field coverage was incomplete. The validator was split into byte-pinned public
validation plus a directly tested pure semantic seam, every nested field became
exact, and the matrix was expanded before final review.

The final independent security review found no P0/P1. Its sole P2 was that the
documented checker digest needed to be described as externally anchored rather
than self-enforced; the design and report now state that boundary explicitly.

## Non-claims

This result does not authenticate a person, key, signature, review, custody
claim, manifest, repository, clock, replay ledger, or capability. It does not
freeze a corpus, open G1.4, grant candidate access or implementation, execute
BioCortex, mutate retrieval, write live state, or promote runtime.
