# Engram G1.3 Structural Corpus-Freeze Review Gate Result

Date: 2026-07-18

Status: **PASS / STRUCTURAL FREEZE REVIEW ONLY / SECURE CUSTODY REQUIRED / NO AUTHORITY**

## Result

The hardened G1.3 contract, input-chain validator, two-reviewer structural
freeze validator, structural custody-attestation validator, and adversarial
suite pass. The gate fixes the future freeze-review protocol while keeping every
operational authority and candidate-protocol preregistration readiness false.

The imported G1.3 draft at `98fc4a64b5745e45a07285b0049c9daff89359ef`
treated a caller-controlled `consumer_owned_real` label plus ignored-path
placement as sufficient to set freeze authority and G1.4 readiness. This result
supersedes that authority model. A claimed-real double endorsement can now only
report structural completion while requiring a separately preregistered
secure-custody and authenticated-authority adapter. It is not ready for
authenticated review.

The checker used no authenticated real-world role, review, owner-decision,
corpus-manifest, or freeze evidence. It temporarily created synthetic packets
relabeled claimed-real under ignored `data/`, exercised the laundering path,
and removed them. In normal use the validator can structurally read
caller-supplied claimed-real packets but does not authenticate their contents or
path custody. No raw query, target key, episode-group membership, partition
membership, identity, or sealed material entered public artifacts.

## Binding

- G1.1 preflight commit:
  `3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`;
- G1.1 contract SHA-256:
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`;
- G1.1 validator SHA-256:
  `f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`;
- hardened G1.2 commit:
  `400550236a643867086464e681be1fd5d12e579f`;
- G1.2 contract SHA-256:
  `f8c6cb0784b9981d5f9492bfa5d3539972e9eda2a0c28568ecda251c3f1c9e35`;
- G1.2 validator SHA-256:
  `98c71e96cfc05552ed5fecfb92f74066d3e0ddab173015f64abede730545a3a6`;
- G1.3 contract SHA-256:
  `5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504`;
- G1.3 validator SHA-256:
  `0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089`;
- G1.3 checker SHA-256:
  `e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39`.

The predecessor files remain unchanged. G1.3 hashes and invokes both exact
predecessor validators before it evaluates a freeze-review packet.

## Structural proof

The positive synthetic chain contains five distinct role holders, separate
application-owner and independence-auditor approvals, a structural owner
endorsement, a complete 30-group manifest with 540 baseline observations, two
appointed freeze-review endorsements, and a matching structural custody
attestation.

Its final verdict is
`SYNTHETIC_FREEZE_ENDORSEMENT_VALID_NO_AUTHORITY`. Structural validity is true,
while assembly authority, freeze authority, all candidate/data/runtime
authorities, and G1.4 readiness remain false.

The mutation suite rejects:

- contract relaxation or manifest substitution permission;
- owner rejection and manifest assembly before owner endorsement;
- role, review, owner-decision, or manifest byte-binding drift;
- freeze review starting before manifest assembly;
- candidate, duplicate, or outsider reviewer commitments;
- endorsement with an incomplete registered check;
- placeholder or duplicate review receipts;
- wrong custodian, receipt reuse, or changed-manifest custody;
- candidate-authored freeze review or raw identity fields;
- human-readable packet identifiers;
- packet identifiers aliasing holder, prior-review, or custody SHA-256 values;
- packet identifiers, owner/review/custody receipts, private group identifiers,
  or other redacted SHA-256 values aliasing public contract, validator, or
  whole-packet receipt digests;
- claimed-real packets outside ignored `data/`;
- duplicate JSON keys.

One reviewer rejection is accepted only as
`SYNTHETIC_FREEZE_REJECTION_VALID_NO_AUTHORITY` and cannot advance any gate.

## Laundering regression

The checker copies the complete synthetic role, role-review, owner-endorsement,
manifest, and freeze-review chain into ignored `data/`, relabels every packet
`consumer_owned_real`, repairs all packet-byte hashes, and checks both the
intermediate chain receipt and final freeze receipt. The validator may classify
the result as
`CLAIMED_REAL_FREEZE_ENDORSEMENT_REQUIRES_SECURE_CUSTODY_CAPTURE`, and explicitly
keeps secure-custody verification and authenticated-review readiness false,
along with all of the following:

- authenticated freeze authority verified;
- private-corpus assembly authority;
- G1 corpus-freeze authority;
- candidate-protocol preregistration readiness;
- candidate manifest and FIT access;
- candidate implementation;
- BioCortex experiment execution;
- retrieval-order mutation;
- live-store writes;
- runtime promotion.

This proves that evidence-class relabeling, ignored-path placement, complete
attestations, and local structural validation cannot mint authority.

An independent review found that read-before-path-check handling of
caller-controlled files could otherwise issue a misleading structural
authentication-readiness receipt after a path swap. G1.3 closes that path
fail-closed: it makes no secure-custody claim and emits no authentication
readiness. Implementing no-follow retained-identity capture belongs to the
separately preregistered successor adapter.

The same review cycle found that a private value could have aliased a public
receipt digest while the redacted receipt claimed that private value was absent.
G1.3 now rejects that cross-namespace alias across the complete input chain and
freeze packet. A table-driven nine-case matrix covers chain packet IDs, holder
commitments, owner receipts, group IDs, query commitments, target commitments,
current review receipts, custody receipts, and freeze packet IDs. Its targets
span public contract, current and predecessor validator, and whole-packet
digests, and every case must reach the dedicated alias guard rather than fail
for an unrelated structural reason.

## Verification

Passed:

- `scripts/check-engram-g0-failure-intake.sh`;
- `scripts/check-engram-g1-corpus-design.sh`;
- `scripts/check-engram-g1-freeze-preflight.sh`;
- `scripts/check-engram-g1-role-review.sh`;
- `scripts/check-engram-g1-corpus-freeze-review.sh`;
- Python compile, Pyflakes, Black, and Bash syntax checks;
- deterministic double-run and outside-working-directory checks;
- redacted-receipt group/query/target, commitment, receipt, and packet-ID
  exclusion checks, including cross-namespace public-digest alias regressions;
- nine-case redacted/public SHA-256 alias matrix spanning contract, current and
  predecessor validator, and whole-packet digest categories;
- forged synthetic-to-claimed-real laundering regression under ignored
  `data/`, with every authority field false;
- changed-file scan for checked-in real evidence packets: zero files;
- `git diff --check`.

## Authority boundary

G1.3 is a structural endorsement gate only. It does not authenticate people,
appointments, signatures, review acts, custody, evidence truth, canonical-path
identity, or authority. Its receipt is not secure-custody evidence. A future
authenticated adapter must be independently preregistered and threat-reviewed,
then securely reopen and revalidate the exact originals before any authority can
become true.

## Next gate

G1.4 candidate-protocol preregistration remains closed. The next admissible work
is design-only preregistration of the authenticated authority adapter itself,
including trust anchors, domain-separated signatures, replay protection,
canonical repository/path binding, no-follow file access, retained file
identity, hardlink policy, and exact predecessor/scope binding. That design does
not authorize implementing or enabling the adapter.
