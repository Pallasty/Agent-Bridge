# BioCortex Track B S21B-A0: non-live presign closure and role-artifact existence audit

Date: 2026-07-18

Stage: **S21B_A0_NON_LIVE_PRESIGN_CLOSURE_AND_ROLE_ARTIFACT_EXISTENCE_AUDIT**

Status: **S21B_A0_BLOCKED_MISSING_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES**

Decision: **S21B_A0_REMAINS_BLOCKED_NO_UNSIGNED_SUBJECT_OR_OWNER_SIGNING_REQUEST**

Implementation mode: **READ_ONLY_IDENTITY_AND_EXISTENCE_AUDIT_WITH_SYNTHETIC_BLOCKED_RECEIPT_ONLY**

Owner interaction required now: **NO**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Purpose

S21B-A0 inserts a fail-closed presign audit between S21A tooling completion and
generation of any owner-review subject. It prevents a well-formed nonzero digest
from being substituted for a build artifact that does not exist and prevents an
underspecified toolchain, feature set, or schema set from being presented to the
owner as a closed signing subject.

This stage is deliberately blocked. It defines one closed Draft 2020-12 receipt
schema and one synthetic blocked KAT. It does not generate a final-refreeze
subject, owner signing request, signing message, trust anchor, key, signature,
external-input admission result, execution capability, or live action.

## Exact S21A target that can be audited

The current post-integration target is:

- S21A source commit `ed5d959489f88d0eead21b604d03a142e0584982`;
- S21A source tree `7d1db2c9eb04d75cc980ea83d369b9129155252f`;
- S21A integration commit `34b1c7e6ca9c2b75fd2ef3cf418a444353059511`;
- S21A integration tree `00bbf534c33ecfa56d05579d8a7f4c83e60b208e`;
- integration first parent `8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5`;
- integration second parent `ed5d959489f88d0eead21b604d03a142e0584982`;
- exact archive profile
  `git -c tar.umask=0022 archive --format=tar <commit>`;
- observed integration archive SHA-256
  `d45312d5b343dd036ef6906af0abe9f59da8220cf6ef16fb87caf8c1265c0bb5`;
- `Cargo.lock` raw SHA-256
  `408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59`.

These identities and observations are independently recomputable. They are not
by themselves a complete presign closure. A real audit receipt must recompute
the Git object relationships, two-parent topology, exact archive bytes, and
`Cargo.lock` bytes without copying expected values from a candidate subject.

## Blocking role-artifact finding

The S21A final-subject contract names four build products:

1. controller binary;
2. observer binary;
3. runner binary; and
4. validator binary.

The frozen `ab-store` Cargo manifest declares only the unrelated
`backfill-embeddings` binary. The four required named role binaries have no
declared Cargo target, exact artifact path, independently defined build recipe,
or real artifact digest. Private library modules and a Cargo test executable are
not silently reclassified as these four role binaries. One arbitrary nonzero
digest, four synthetic digests, or one shared test-binary digest cannot close
this requirement.

If the role artifacts are added or their meaning is changed in repository code,
the resulting new integration commit and tree become the next refreeze target.
The older `34b1c7e6...` identity must not be presented as if it contained those
new artifacts.

## Missing reproducible closures

The following canonical definitions and receipts are absent:

- a toolchain-manifest field set, ordering, encoding, target triple, and digest
  derivation profile;
- a complete Cargo feature-set membership, ordering, encoding, and digest
  derivation profile;
- a schema-set file membership, mode, ordering, framing, and digest derivation
  profile;
- exact deterministic build recipes for each named role artifact;
- two independent clean-archive rebuild receipts; and
- equality evidence for every role artifact and closure digest across both
  rebuilds.

Until those definitions exist, the S21A subject fields
`toolchain_manifest_sha256`, `feature_set_sha256`, `schema_set_sha256`, and the
four role-binary digests are unfilled requirements, not values that may be
chosen merely because they match a SHA-256 lexical form.

## Closed blocked receipt

The S21B-A0 receipt uses:

- schema
  `agent_bridge.memory_temporal_owned_lab_presign_closure_receipt_s21b_a0.v0`;
- packet kind `S21B_A0_PRESIGN_CLOSURE_RECEIPT`;
- canonicalization
  `AB_RESTRICTED_CANONICAL_JSON_S21B_A0_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT`;
- digest domain
  `agent-bridge/biocortex/owned-lab/s21b-a0/presign-closure-receipt/v1`;
- framing
  `U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD`;
- self field `presign_closure_receipt_sha256`, excluded exactly once; and
- repository framing of canonical payload followed by one LF, with that LF
  excluded from the digest.

The schema is closed, local-reference-only Draft 2020-12. It rejects unknown
fields, floats, negative or overflowing integers, malformed or all-zero
security digests and Git OIDs, and any blocked receipt that claims a role
artifact, rebuild closure, subject, signing request, key, anchor, signature,
permit, or live authority is present.

The committed fixture is `test_only=true`, `synthetic=true`, and remains in
state
`SYNTHETIC_KAT_BLOCKED_MISSING_FOUR_ROLE_ARTIFACTS_AND_REBUILD_CLOSURES`.
Its exact Git/archive values are stable audit KAT inputs, not proof that a real
presign audit ran.

## Exit conditions for S21B-A1

Advancement to a subject-generation stage requires all of the following:

1. four exact named non-live role artifacts exist under frozen build recipes;
2. toolchain, feature-set, and schema-set canonical closures are defined;
3. two isolated clean-archive rebuilds independently produce identical hashes;
4. Git topology, archive, `Cargo.lock`, role artifacts, and all closure digests
   are independently recomputed without candidate-supplied expected values;
5. the final target integration identity includes every change needed to create
   those artifacts and definitions; and
6. a separate review confirms that subject generation still produces no owner
   authority or execution capability.

Only after those conditions pass may a new stage generate and independently
verify an unsigned final subject. Owner anchor provisioning and owner signing
remain later boundaries. The user does not need to sign or provide a private key
during S21B-A0.

## Nonclaims

S21B-A0 does not claim that:

- the observed archive digest is a complete build provenance proof;
- private Rust modules are deployed controller, observer, runner, or validator
  binaries;
- schema validity proves any missing artifact exists;
- a blocked audit receipt is an unsigned final subject;
- a blocked audit receipt may be signed;
- an owner trust anchor is installed or pinned;
- an owner private key or signature is present;
- external inputs are admitted;
- an execution permit exists; or
- any live or application side effect is unlocked.

`side_effects_unlocked` remains `NONE`.
