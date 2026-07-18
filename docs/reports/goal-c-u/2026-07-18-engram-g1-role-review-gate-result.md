# Engram G1.2 Role-Review Gate Result

Date: 2026-07-18

Status: **PASS / PRIVATE ROLE REVIEW ONLY**

## Result

The G1.2 public contract, role-review validator, owner-decision validator, and
synthetic negative gates pass. The new gate closes the gap between a
structurally valid role roster and permission to assemble private corpus
material.

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
  `efb7464e2922d0dd2645698435272714316d07f786bd5a56114e900b99e31f6c`;
- G1.2 validator SHA-256:
  `5efe72815341492b84a4bd0dee487d1eb572e60e7938f3df7e5cb9710ef8706f`;
- G1.2 checker SHA-256:
  `a3e2824ca764d9a316d0509f2da6257e473bd34a605c1149c5ecfee3255c320a`.

The predecessor files remain unchanged. G1.2 validates G1.1 role packets
through the bound predecessor validator before it evaluates any review.

## Separation and chronology

The application owner may overlap only the consumer curator. The owner cannot
overlap the candidate implementer, freeze reviewers, or sealed custodian. The
independence auditor must be outside all five role holders and distinct from
the owner.

Review must start after the role packet and complete before the owner decision.
Every transition binds the exact prior packet bytes. A later approval cannot be
replayed against a changed role or review packet.

The validator checks these structural relationships and private commitments.
It does not authenticate real-world identities, appointments, evidence truth,
or organizational authority.

## Synthetic proof

The positive fixture exercises an owner who is also the consumer curator, an
outside independence auditor, two approving reviews, and an approving owner
decision. Its receipt is
`SYNTHETIC_APPROVAL_VALID_NO_AUTHORITY`: it is structurally approvable but
grants no private assembly permission.

Negative cases reject owner/candidate overlap, false curator matching,
auditor/holder overlap, reversed chronology, candidate authorship, unsalted
commitments, raw identity fields, placeholder receipts, byte-binding drift,
scope widening, approval after a rejected audit, real packets outside ignored
`data/`, and duplicate JSON keys. A rejected audit can be followed only by an
owner record rejecting the role roster.

## Verification

Passed:

- `scripts/check-engram-g0-failure-intake.sh`;
- `scripts/check-engram-g1-corpus-design.sh`;
- `scripts/check-engram-g1-freeze-preflight.sh`;
- `scripts/check-engram-g1-role-review.sh`;
- Python compile and deterministic double-run checks;
- outside-working-directory invocation check;
- fail-closed synthetic mutation suite;
- direct redacted-receipt scan for holder, reviewer, appointment, review, and
  authorization commitments;
- scan of all six changed files against 12 protected G0 query/target literal
  occurrences: zero matches;
- changed-file scan for real role/review/decision evidence: zero files;
- `git diff --check`.

## Authority boundary

The checked-in public contract and all checked-in synthetic evidence grant no
authority. A future real double-review plus real owner approval can authorize
only consumer-curator intake under ignored `data/`, read-only replay on
disposable snapshots, and preparation of a hash-only manifest for later freeze
review, capped at 36 groups.

The following remain false even after that narrow authorization:

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
decision that opens curator-only intake. A later freeze-review gate is still
required before any corpus can be frozen.
