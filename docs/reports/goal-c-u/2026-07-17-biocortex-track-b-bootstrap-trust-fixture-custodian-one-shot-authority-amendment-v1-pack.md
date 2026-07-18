# Track B bootstrap-trust fixture-custodian one-shot authority amendment v1

Date: 2026-07-17

Status: owner-authorized amendment recorded; effective only after an ordinary
two-parent integration and a passing full source-bound replay.

## Outcome

The owner explicitly authorized the narrow resolution proposed after the
positive-KAT material gap was discovered.  This pack does not generate a key,
does not sign a message, and does not consume the already-effective verifier
implementation authority.  It records a separate, one-shot fixture-custodian
authority whose sole purpose is to supply the missing nonsecret public KAT
material.

The frozen decision record is
`scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_owner_decision_v0.json`.
Its raw SHA-256 is
`d913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f`.
The normalized contract SHA-256 is
`c473be2365a38addebf6565932eeb811636401d8bef8129b791af662733d77fe`.
The pack manifest raw SHA-256 is
`0264011a5dfd046378c5e35acb8050d4753f6d487c0caa73e23cce4dc1eaaf41`.

## Contract clarification

For each of the managed and self-hosted profiles, the three entries are a
separately injected, pinned structural policy chain:

1. synthetic root;
2. synthetic issuer;
3. active synthetic leaf.

No root self-signature, certificate-link signature, or PKI path-validation
subject/domain is introduced.  The positive path performs exactly one pure
RFC8032 Ed25519 verification: the active leaf signature over the already
frozen domain-and-exact-frame message.

The generic KAT classification
`SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY` maps only as follows:

- `MANAGED_SPANNER_CLOUD_KMS` →
  `KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER`;
- `SELF_HOSTED_ETCD_OPENBAO` →
  `KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER`.

The mapping is derived from the separately injected policy.  It cannot be
supplied or overridden by the detached bundle or envelope.  It is not signer
role/scope authorization, does not implement T06, and does not implement a
track-subject, audience, or nonce control.

## Exact generation ceremony

After this amendment's integrated full gate passes, one semantically distinct
fixture custodian may start one foreground offline process.  The authority is
consumed at
`FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN`.  A crash,
empty output, validation failure, or any later drift remains terminal and does
not authorize a retry.

The process may use only the existing cached and locked `ring 0.17.14` with
`CARGO_NET_OFFLINE=true`, without changing repository Cargo files.  It may use
the local OS CSPRNG and must perform exactly:

- six ephemeral keypair generations: root, issuer, and active leaf for each
  track;
- two signatures: one active-leaf signature for each exact track message;
- zero revoked-leaf key generations;
- zero chain-link or certificate signatures.

Private bytes remain process-memory-only and may not enter a file, environment
variable, log, stdout, stderr, Git object, or committed artifact.  The
ephemeral generator source, executable, and build namespace are not committed.
Scratch directories and the ephemeral executable are restricted to `0700`;
non-executable scratch data files are restricted to `0600`.
Namespace cleanup is recorded without claiming secure erasure, memory
zeroization, or swap exclusion.

Only six raw 32-byte public keys, two raw 64-byte signatures, and a nonsecret
public provenance receipt may enter the subsequent supply pack.  Network,
provider, credential, production-root, trusted-time, external-spend, runtime,
and real-evidence authority all remain zero or false.

## Separation of duties

The frozen ceremony and final implementation require four pairwise-distinct
semantic actors:

- fixture custodian;
- verifier implementer;
- contract/provenance reviewer;
- crypto/security/source-bound reviewer.

No lane is represented as a production security approval, and semantic labels
are not represented as cryptographically authenticated identities.

## Independent checking

The source and independent checker reject duplicate JSON keys and bind the
complete owner record as a closed-world canonical object.  The checker also
binds every manifest field, every path/mode, all fifteen dependency hashes,
and both predecessor authority receipts.  It independently reads the frozen
frame fixture and reconstructs both length-prefixed signature messages before
checking their frame length, message length, SHA-256, and SHA-512 anchors.

## Source binding and release

The source commit must have sole parent
`a18f0af7b4cbaa971143c71080a2b49786a7f7a3` and add exactly the seven pack
paths.  A full replay is release-capable only on an ordinary two-parent merge
whose first parent descends from that baseline and excludes the source commit.

The gate directly archives this seven-path pack, the seven-path underlying
implementation-authority pack, and the eight-path frame/mode dependency pack.
It replays the underlying authority from its frozen integration and verifies
that it is effective and still unconsumed.

Fast replay remains non-release and does not make the fixture authority
effective.  Integrated full replay makes the fixture authority effective but
does not consume it.  Neither path consumes the original verifier
implementation authority.

## Nonclaims

This record is not key provisioning, production trust, a provider
compatibility result, runtime execution, evidence authentication, T06
authorization, scientific evidence, application evidence, or production
security approval.  `global_single_use_proved` remains false because no
external single-use ledger is bound.
