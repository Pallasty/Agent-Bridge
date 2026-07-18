# Track B bootstrap-trust public-only vector supply and generation provenance receipt freeze v1

Date: 2026-07-17

Frozen source baseline: `b4126a4192137e741e32ebb86170884b81185cbf`

Decision: `CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE`

## Outcome

The one-shot fixture-custodian ceremony authorized by the integrated amendment
completed successfully.  This pack freezes only its nonsecret public output:
six raw Ed25519 public keys, two raw Ed25519 signatures, and the public
generation-provenance receipt.  It contains no seed, private key, PKCS#8, PEM,
generator source, generator executable, credential, endpoint, or production
trust root.

The fixture-generation authority is now consumed.  It cannot be restored by a
Git revert and does not authorize another process entry.  The separate T05
bootstrap-trust verifier implementation authority remains effective and
unconsumed; this supply pack does not implement or consume that successor.

## Ceremony evidence

The authority amendment full replay completed at integration commit
`b4126a4192137e741e32ebb86170884b81185cbf`.  Its 54-line receipt has SHA-256
`a40e9a208209de3a24904dc0957515e11f247ee7e07c070ff2306f32e553d77f`,
and the amendment gate raw SHA-256 is
`21c5aa21cebf7e37767a2ec0bcd38bd8b28839bd9b825c86e81920a2ce20aef0`.

One semantically distinct fixture custodian compiled an ephemeral Rust
generator against cached, locked `ring 0.17.14` with
`CARGO_NET_OFFLINE=true`.  The final ephemeral source SHA-256 was
`62a8e32eef9e9a5560cd6dacfce5a181761196cef18a77508eb8552c1e20f083`.
The runtime pin was:

```text
rustc 1.96.0 (ac68faa20 2026-05-25); cargo 1.96.0 (30a34c682 2026-05-25); host x86_64-unknown-linux-gnu
```

After all static checks, the executable was entered exactly once.  Process
entry consumed the authority before randomness or key generation.  It exited
zero after 3,436,927 ns with empty stdout and stderr.  No retry occurred.  It
performed exactly six ephemeral keypair generations and two active-leaf
signatures, with zero revoked-leaf key generation and zero certificate-link
signatures.

Private material remained generator-process-memory-only according to the
frozen public receipt.  The process removed its source, executable, build
output, message scratch files, and scratch namespace before emitting a receipt
with `generator_namespace_cleanup_complete=true`.  Namespace removal is not a
secure-erasure, private-memory-zeroization, or swap-exclusion claim.

During startup preparation, before generator entry and before authority
consumption, an ephemeral source-draft tool initially inherited the
`biocortex-rs` working directory.  The two transient local edits were handled
by two distinct reversible actions: the
untracked `src/main.rs` draft was moved to the designated scratch namespace,
while the draft `Cargo.toml` content was copied there before the repository
`Cargo.toml` was restored to its original bytes by an exact patch.  The
repository blob, index, and worktree identities were independently confirmed
equal before build.  Both
`biocortex-rs` and `agent-bridge` were clean before the one allowed process
entry.  This did not create a second generation attempt.

## Frozen public artifacts

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| Public vector bundle | 3,784 | `a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7` |
| Public generation receipt | 1,201 | `bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0` |

The compact pack manifest has raw SHA-256
`451e05a19e1b30c70dbb7606ccc6f438cbee69595f8e8b7576fa255ef4ec91d7`.

Both are duplicate-key-safe, sorted-key compact UTF-8 JSON with exactly one
trailing line feed.  The bundle is a closed seven-field top-level object and
contains exactly two tracks in the frozen order:

1. `MANAGED_SPANNER_CLOUD_KMS`
2. `SELF_HOSTED_ETCD_OPENBAO`

Each track contains one structural three-entry policy chain in root, issuer,
active-leaf order.  All six committed raw 32-byte public points are pairwise
different.  The revoked-leaf object contains only the frozen key identifier,
revoked v1 version, and revoked-at-or-before-snapshot state; it has no public or
private key material.  Each track contains one raw 64-byte active-leaf
signature.

## Message and cryptographic validation

The validator reconstructs each message from the exact frozen predecessor
frame bytes:

```text
u64be(len(domain)) || ASCII domain ||
u64be(len(exact raw canonical predecessor frame)) || raw frame
```

| Track | Frame bytes | Message bytes | Message SHA-256 |
|---|---:|---:|---|
| Managed | 659 | 754 | `a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b` |
| Self-hosted | 658 | 757 | `2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac` |

The supply validator contains verify-only RFC8032 reference arithmetic.  It
has no key-generation, public-key derivation, signing, provider, credential,
network, or mutable-cache surface.  It requires canonical point encodings,
on-curve points, nonidentity points, prime-order-subgroup membership for both
public key and signature R, and `S < L`.  All six public points and both
signatures pass.  The positive cryptographic operation remains exactly one
active-leaf signature verification per track; root and issuer entries are
structural frozen-policy inputs, not certificate signatures.

The independent checker also rejects 33 directed mutations covering duplicate
keys, noncanonical JSON, extra/private fields, track and chain substitution,
role and key-version drift, policy and revocation drift, cross-track
signatures, identity/small-order or duplicate keys, invalid R and S, message
and frame drift, receipt authority/count drift, network/private-write drift,
cleanup drift, secure-erasure overclaim, and predecessor-frame substitution.

## Quantitative definitions before values

- **Public-key count** is the number of raw 32-byte public values in the two
  frozen three-entry structural chains.  It is not a security-strength or
  entropy estimate.
- **Strict point-validation count** is the number of those public values that
  passed the explicit encoding, curve, identity, and subgroup checks.
- **Signature-verification count** is the number of active-leaf RFC8032
  equations evaluated against the two exact KAT messages.
- **Directed mutation count** is the number of constructed invalid public
  objects rejected by the independent checker.  It is not code coverage,
  proof of completeness, or an error probability.
- **Process-entry and retry counts** are frozen ceremony observations, not an
  externally witnessed global single-use ledger.

| Frozen diagnostic | Value |
|---|---:|
| Process entries | 1 |
| Retries | 0 |
| Ephemeral keypairs generated | 6 |
| Signatures generated | 2 |
| Revoked-leaf keypairs generated | 0 |
| Certificate-link signatures generated | 0 |
| Public keys frozen | 6 |
| Pairwise-distinct public keys | 6 |
| Strict public-point validations | 6 |
| Active-leaf signature verifications | 2 |
| Directed mutations rejected | 33 |
| Network attempts | 0 |
| Provider calls | 0 |
| Credential accesses | 0 |
| Private-material file writes | 0 |
| Committed private-material items | 0 |

No chart is used because these are categorical contract counts, not a trend,
distribution, throughput comparison, or effect magnitude.

## State and authority boundary

This pack changes only the fixture-generation state:

```text
AUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START
  -> CONSUMED_PROCESS_STARTED_OUTPUT_PENDING
  -> CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE
```

It does not consume the separately frozen implementation authority.  That
authority permits the next source unit to implement only the isolated-lab
synthetic bootstrap-trust verifier.  It still does not authorize production
runner launch, provider access, credentials, deployment, real evidence
acceptance, condition output, or external spend.

## Nonclaims

- No global single-use proof from an external ledger.
- No secure erasure, memory zeroization, or swap exclusion proof.
- No production authentication, PKI path validation, or certificate-chain
  signature claim.
- No role/scope authorization or track-subject authorization implementation.
- No claim that the frozen revocation snapshot is current now.
- No provider cryptographic-compatibility or production-security approval.
- No runtime prerequisite, production ingestion control, or production threat
  execution.
- No real evidence, experiment row, application, scientific, product, memory,
  retrieval, storage-efficiency, or biological-brain conclusion.

## Next unit

The next source unit is exactly:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

It may consume these public vectors, but must continue to accept four disjoint
inputs, reject production/unknown mode before observing the other inputs, call
the frozen predecessor frame reviewer in synthetic mode, validate the
separately injected structural trust policy, perform exactly one active-leaf
signature verification, and remain fail-closed on exact key-version, role,
policy, revocation, root, issuer, track, frame, domain, and signature drift.
