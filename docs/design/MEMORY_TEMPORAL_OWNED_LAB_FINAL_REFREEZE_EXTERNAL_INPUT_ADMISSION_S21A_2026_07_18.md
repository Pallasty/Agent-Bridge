# BioCortex Track B S21A: final-refreeze and external-input admission tooling

Date: 2026-07-18

Status: **S21A_NON_LIVE_REFREEZE_AND_EXTERNAL_INPUT_ADMISSION_TOOLING_COMPLETE**

Decision: **S21B_BLOCKED_PENDING_POST_INTEGRATION_UNSIGNED_FINAL_SUBJECT_NEW_OWNER_SIGNATURE_INSTALLED_TRUST_ANCHOR_AND_INDEPENDENT_LIVE_INPUTS**

Implementation mode: **PRIVATE_DEFAULT_OFF_SYNTHETIC_NON_LIVE_REFREEZE_AND_ADMISSION_VALIDATION_ONLY**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Purpose and predecessor boundary

S21A defines the closed documents needed to prepare a separately reviewable S21B
owner decision without pretending that repository fixtures are authority. It
freezes the completed S20B predecessor integration
`33c2c4df78ef302fd0538986b95fa40a3711ba86` and tree
`6f92c687b61e1433e693ca6cd1bc6390dda97f29`, plus the S20B source commit
`a1948daaf466563358fcbf054b2bebef8e966777` and tree
`eca0de065221621fcc70941adaefac1f4315bd3e`.

This stage adds schemas, synthetic blocked KATs, private typed builders/parsers,
semantic admission validators, an independent checker, and a release gate. All
runtime code is default-off and consumes only explicit bytes plus caller-pinned
expectations. It does not install an owner key, sign a final subject, instantiate
a checkpoint provider, register an authorization row, observe a live environment,
launch a runner, claim a permit, or execute a canary. No existing S19 signature
or envelope binds S20A, S20B, or S21A additions.

## Four closed packet roles

All four packets use Draft 2020-12 closed schemas, ASCII-only restricted
canonical JSON, no floating-point values, SHA-256, unique domains, explicit
U32BE/U64BE framing, and exactly one excluded top-level self-digest field. Every
required security digest, Git OID, Ed25519 public key, and detached signature
rejects the all-zero representation. Candidate-reported digest matches are never
authoritative.

1. The final-refreeze subject binds the predecessor identities and the complete
   future S21A integration/build/artifact identity. The repository fixture is
   deliberately synthetic and leaves every future S21A commit/tree binding null.
2. The owner trust anchor binds a new S21A audience, owner role, Ed25519 public
   key identity, trust policy, key version, and installation evidence. The
   repository fixture is a public KAT in state
   `SYNTHETIC_PUBLIC_KAT_NOT_INSTALLED`. Its key identifier and key material are
   test vectors only and are denylisted for every real (`test_only=false`)
   anchor.
3. The owner authorization envelope binds the exact final subject and pinned
   anchor using the new signature domain
   `agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signature/v1` and
   audience
   `agent-bridge/biocortex/owned-lab/s21a/final-refreeze-owner-review/v1`.
   Reuse of any S19 signature or envelope is forbidden.
4. The external-input admission packet binds independently supplied checkpoint,
   registration, observer, runner, environment, STOP/revocation, retention,
   cleanup, custody, and review facts. Even a complete packet is only an input
   validation result and still requires separate review; it is never a permit.

## Post-integration final refreeze

A real unsigned final subject cannot be committed as a repository fixture because
it must bind the S21A source commit, source tree, final two-parent integration
commit and tree, exact archive, binaries, toolchains, feature set, schemas,
assignment and operation ABI, catalog, and validator ruleset. Binding its own
future commit from inside that commit would be cyclic.

The real unsigned subject therefore MUST be generated outside the repository,
after S21A integration, from an exact clean archive and independently recomputed
build receipts. The generator must not copy expected hashes from a candidate
subject. Any subsequent change to source, tree, schema, binary, toolchain,
feature set, assignment, operation descriptor, catalog, ruleset, or policy
invalidates the subject and requires a new refreeze and owner decision.

## Owner trust and signature separation

The envelope cannot authenticate its own key. A caller must independently pin
the canonical trust-anchor document digest and verify that its installation and
owner-identity evidence came from an out-of-band path. A real installed anchor
must bind both `owner_identity_sha256` and a nonzero
`owner_identity_verification_receipt_sha256`; the synthetic public KAT forces the
receipt to null and `identity_verified_out_of_band=false`. A repository public key,
test vector, candidate-carried key, self-installed anchor, or old S19 key/signature
cannot establish S21 authority.

The real-anchor validator and schema apply an explicit repository KAT denylist.
For `test_only=false`, either key identifier
`s21a-synthetic-public-kat-v1` or public key
`d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`
hard-fails the anchor, even when the candidate marks it installed and the caller
pins matching bytes. The same identifier and key remain valid only in the
committed `test_only=true`, `synthetic=true`, not-installed KAT so its stable
self-digest can test canonicalization and validation without creating S21
authority.

The owner signature is over the new S21A domain and exact canonical payload
digest. Schema validity, a self-reported `signature_verified` value, or a valid
synthetic signature is not owner authority. A final signature can be requested
only after the post-integration unsigned subject has been independently rebuilt
and reviewed.

The signed-payload digest is:

```text
SHA256(U32BE(len(signed_payload_domain)) || signed_payload_domain ||
       U64BE(len(canonical_signed_payload)) || canonical_signed_payload)
```

where `signed_payload_domain` is
`agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signed-payload/v1`.
The Ed25519 message uses the distinct signature domain and frames the raw
32-byte signed-payload digest as
`U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_SIGNED_PAYLOAD_SHA256`. The detached
signature digest is `SHA256_RAW_64_BYTE_ED25519_SIGNATURE`.

The authorization ID uses domain
`agent-bridge/biocortex/owned-lab/s21a/owner-authorization-id/v1` and profile
`U32BE_DOMAIN_LENGTH_DOMAIN_THREE_U64BE_32_RAW_SHA256`. Its three ordered frames
are the raw signed-payload digest, raw detached-signature digest, and raw anchor
document digest. None of these values may be accepted from the candidate without
independent recomputation.

## Independent external inputs

S21B remains blocked until all of the following are independently supplied and
bound to the same final subject and owner envelope:

- an installed and caller-pinned owner trust anchor and a new owner signature;
- a real monotonic checkpoint provider outside the database, directory,
  filesystem, and rollbackable failure domain, with exact provider trust-anchor,
  provider/database failure-domain, receipt, current head, content-root,
  predecessor, observed-revocation-epoch, and acknowledgement bindings;
- an external `AUTHORIZED_UNCLAIMED` registration that was not created by the
  runner and exactly binds authorization ID, final-subject digest, owner-envelope
  digest, capability nonce, registrar and external-control-plane identities,
  provenance receipt, creator binary, expected-unclaimed/previous/current
  revisions, successful-claim count, and nullable claimed-run identity;
- fresh STOP and revocation reads, a fresh observer, exact controller and runner
  builds, exact owned-lab root/device/mount/kernel facts, and exact canary inputs;
- one-shot reservation and claim bindings, zero retry, and exact 60/59/59/113
  accounting; and
- retention, cleanup, custody, and independent review policy and receipt inputs,
  including the exact independent-review receipt and current revocation epoch.

Missing, stale, forked, PREPARED, rollback-detected, acknowledgement-unknown,
self-asserted, same-failure-domain, reused-signature, build-drift, or
runner-created input hard-locks admission. Unknown state is never converted to a
false, zero, or success value.

Both the checkpoint and registration independently repeat the authorization ID,
final-subject digest, and owner-envelope digest so the semantic validator can
compare them with the verified top-level subject and owner bindings. The
registration additionally repeats the capability nonce. Checkpoint counter 1
requires a null predecessor; every later counter requires a non-null exact
previous-checkpoint digest. Candidate equality booleans are not authoritative.
The checkpoint's observed revocation epoch and the policy's current revocation
epoch must both equal the owner-signed current epoch. Its provider and database
failure-domain digests must be distinct. The registration creator binary must
not equal the bound runner binary.

For an `AUTHORIZED_UNCLAIMED` registration,
`expected_unclaimed_revision == registration_revision`,
`previous_revision + 1 == registration_revision`, successful claims are zero,
and the claimed-run digest is null. The synthetic missing-row KAT uses previous
revision 0 and expected/current revision 1 without claiming row presence.

The schema and typed validator share exact numeric ceilings: catalog rows 5,639,
validator rules 32, target phases 113, Ed25519 key version and revocation epochs
in the closed range 1 through `u32::MAX`, and counters/revisions represented as
bounded unsigned 64-bit integers. The semantic validator independently rejects
zero security digests, a provider failure domain equal to the database failure
domain, revision arithmetic overflow, or schema/Rust field drift.

## Synthetic KAT boundary

Every committed fixture is `test_only=true`, `synthetic=true`, non-live, and
blocked. The subject is unsigned and not final; the anchor is not installed; the
envelope is unverified and cannot authorize; the admission packet has no real
external inputs. All nonclaims require `side_effects_unlocked=NONE`.

Repository test vectors are never eligible owner keys. In particular, relabeling
the public KAT as a real installed anchor is rejected by both key identifier and
key material; schema conformance or caller pinning cannot promote it to S21
authority.

S21A intentionally has no live adapter, opaque live-fact constructor, checkpoint
port, registration writer, runner handle, claim token, affine permit, executor,
credential, private key, provider access, or application side effect.

## S21A completion and S21B boundary

S21A completion means only that the four closed packet contracts, their private
typed builders/parsers/semantic validators, synthetic fail-closed examples,
independent checker, negative mutation matrix, and predecessor-replaying release
gate are complete. It permits generation of an unsigned candidate subject after
integration; it does not preapprove that subject, an owner decision, external
inputs, or execution.

S21B may be considered only after a post-integration unsigned subject exists and
every external input is independently installed or supplied, freshly validated,
and separately reviewed. Until then:

- `live_canary=NOT_RUN`;
- `future_s21b_preapproved=false`; and
- `side_effects_unlocked=NONE`.
