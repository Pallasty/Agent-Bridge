# Engram G1.2 Role-Review Gate Result

Date: 2026-07-18

Status: **PASS / STRUCTURAL ROLE REVIEW ONLY / NO AUTHORITY**

## Result

The G1.2 public contract, role-review validator, owner-decision validator, and
synthetic negative gates pass. The new gate closes the gap between a
structurally valid role roster and a bounded endorsement that can be presented
to a later authenticated authority verifier. It does not grant assembly
permission.

No real appointment evidence was found or created. No role holder, application
owner, or independence auditor was appointed by this change. No private corpus,
query, target key, group membership, partition membership, or sealed material
was read or assembled.

## Binding

- predecessor G1.1 commit:
  `3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`;
- predecessor contract SHA-256:
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`;
- predecessor validator SHA-256:
  `f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`;
- G1.2 role-review contract SHA-256:
  `842a86010b61a030993d37e6cc2b06206315a22a5b319c79dfaf07ed32522c09`;
- G1.2 validator SHA-256:
  `4e61e5910bd20f26d0e10b9306e42f22645195cf85cdba8a10fc4a958318287d`;
- G1.2 checker SHA-256:
  `cae7a3b00f3769e2f035bed27bf8e29d98a81b3f75785cabba2f2c3831ca161e`.

The predecessor files remain unchanged. G1.2 validates G1.1 role packets
through the bound predecessor validator before it evaluates any review.

## Separation and chronology

The application owner may overlap only the consumer curator. The owner cannot
overlap the candidate implementer, freeze reviewers, or sealed custodian. The
independence auditor must be outside all five role holders and distinct from
the owner.

Review must start after the role packet and complete before the owner decision.
Every transition binds the exact prior packet bytes. A later endorsement cannot
be replayed against a changed role or review packet.

The validator checks these structural relationships and private commitments.
It does not authenticate real-world identities, appointments, evidence truth,
or organizational authority.

## Synthetic proof

The positive fixture exercises an owner who is also the consumer curator, an
outside independence auditor, two approving reviews, and an approving owner
endorsement. Its receipt is
`SYNTHETIC_ENDORSEMENT_VALID_NO_AUTHORITY`: it is structurally valid for a
future authentication step but grants no private assembly permission.

Negative cases reject owner/candidate overlap, false curator matching,
auditor/holder overlap, reversed chronology, candidate authorship, unsalted
commitments, raw identity fields, placeholder receipts, byte-binding drift,
human-readable packet identifiers, identifiers aliasing private commitments or
receipts, scope widening, endorsement after a rejected
audit, real packets outside ignored `data/`, and duplicate JSON keys. A
rejected audit can be followed only by an owner record rejecting the role
roster. An adversarial synthetic chain relabeled as real inside ignored `data/`
is accepted only as structurally ready for authentication and still emits zero
assembly authority.

## Verification

Passed:

- `scripts/check-engram-g0-failure-intake.sh`;
- `scripts/check-engram-g1-corpus-design.sh`;
- `scripts/check-engram-g1-freeze-preflight.sh`;
- `scripts/check-engram-g1-role-review.sh`;
- Python compile and deterministic double-run checks;
- outside-working-directory invocation check;
- fail-closed synthetic mutation suite;
- forged synthetic-to-real laundering check under ignored `data/`, with every
  authority field remaining false;
- direct redacted-receipt scan for holder, reviewer, appointment, review, and
  endorsement commitments;
- scan of all six changed files against 12 protected G0 query/target literal
  occurrences: zero matches;
- changed-file scan for real role/review/decision evidence: zero files;
- `git diff --check`.

## Authority boundary

The checked-in public contract and all checked-in synthetic evidence grant no
authority. A claimed-real double-review plus owner endorsement can only become
ready for authenticated authority review. This validator never sets private
corpus assembly authority to true.

Residual path/custody hardening is explicitly deferred to that authenticated
adapter: the current stable byte capture and later ignored-path check do not
prove canonical-repository identity, no-follow traversal for every ancestor,
or unique-inode custody. Those gaps cannot escalate this structural validator
because all authority outputs are hard false.

The following remain false for every output of this validator:

- private corpus assembly;
- candidate-lane corpus assembly;
- G1 corpus-freeze authority;
- candidate implementation authority;
- BioCortex experiment execution authority;
- retrieval-order mutation authority;
- live-store write authority;
- runtime promotion authority.

## Next gate

The next step is external, not an implementation step: the application owner
and an independence auditor outside all five role holders must produce private,
consumer-owned review evidence. If either rejects, the roster returns for
replacement. If both approve, the owner may issue the separately bound private
endorsement. A later adapter must verify domain-separated signatures against
independently configured owner and auditor trust anchors before curator-only
intake can open. A still-later freeze-review gate is required before any corpus
can be frozen.
