# Engram G1.2 Role-Appointment Review

Date: 2026-07-18

Status: **READY FOR PRIVATE ROLE REVIEW PACKETS / NO CURRENT AUTHORITY**

## Decision

G1.2 inserts an independently reviewable authorization chain between the G1.1
role-commitment packet and any private grouped-corpus assembly. A role roster is
not self-authorizing: an application owner and an independence auditor must
review the exact role-packet bytes, and the application owner must then issue a
separate decision bound to the completed review bytes.

The registered public contract is
`scripts/eval/fixtures/engram_g1_role_review_contract_v1.json`, SHA-256
`efb7464e2922d0dd2645698435272714316d07f786bd5a56114e900b99e31f6c`.
It binds G1.1 commit
`3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`, contract SHA-256
`5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`,
and validator SHA-256
`f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`.

This public contract does not observe appointment evidence, assign real people,
or authorize assembly. It defines only the next fail-closed review protocol.

## Authorization chain

The chain has four distinct records:

1. the G1.1 role packet appoints one candidate implementer, one consumer
   curator, two freeze reviewers, and one sealed evaluator/custodian;
2. the application-owner review checks appointment completeness, consumer
   ownership, and authority to run this workflow;
3. an independence auditor checks holder separation, owner overlap, candidate
   exclusions, sealed custody, salt custody, and appointment chronology;
4. the application owner issues a separate approve-or-reject decision after
   both reviews are complete.

The candidate implementer cannot author or approve either review, issue the
owner decision, assemble the private corpus, inspect the private manifest, or
receive sealed material.

## Reviewer separation

Reviewer identities are represented only by privately salted SHA-256
commitments. Raw names, handles, contact data, and identity fields are
forbidden.

The application owner may be the consumer curator. If that overlap is claimed,
the owner commitment must exactly match the sole consumer-curator commitment.
Otherwise, the owner must be outside all five role holders. In either case the
owner can never equal the candidate implementer, either freeze reviewer, or the
sealed evaluator/custodian.

The independence auditor must be outside all five role holders and distinct
from the application owner. Owner and auditor receipts must be non-placeholder
and distinct. The validator verifies commitment equality and inequality, not a
person's real identity, appointment, independence, or authority.

## Private review packet

Actual reviews use schema
`agent_bridge.engram_g1_role_review_packet.v1` and remain untracked under the
repository's ignored `data/` tree. A packet binds:

- the exact G1.2 contract bytes;
- the exact G1.1 role-packet bytes;
- one salted application-owner commitment and review receipt;
- one salted independence-auditor commitment and audit receipt;
- review start and completion timestamps strictly after role appointment;
- explicit approve-or-reject decisions and bounded attestations.

Both reviewers must approve before an owner may approve assembly. A reviewer
rejection is itself a valid structural result, but it cannot be converted into
an assembly approval. The owner may only record `reject_role_roster` for that
chain.

A redacted review receipt contains decisions and hashes of whole packets. It
does not contain holder commitments, reviewer commitments, appointment
receipts, review receipts, raw identities, or raw corpus material. A valid
review packet still grants no authority.

## Private owner-decision packet

Actual decisions use schema
`agent_bridge.engram_g1_role_owner_decision_packet.v1`. They bind the exact
role and review packet bytes, repeat the application-owner commitment from the
review, occur strictly after review completion, and carry a non-placeholder
authorization-receipt commitment.

The only decisions are:

- `approve_private_corpus_assembly` after both reviews approve; or
- `reject_role_roster`.

An approval scope must exactly match the public contract. It cannot be widened
inside a private packet.

## Exact approved scope

Only a structurally valid `consumer_owned_real` chain ending in owner approval
can authorize the following:

- the consumer curator may create a private intake under ignored `data/`;
- the sealed evaluator/custodian retains custody;
- the curator may perform read-only baseline replay on disposable snapshots;
- the curator may prepare a hash-only manifest for later freeze review;
- intake is capped at 36 episode groups.

Even that approval does not freeze the corpus. It does not authorize candidate
implementation, BioCortex experiment execution, retrieval-order mutation,
live-store writes, or runtime promotion. The candidate lane may not execute the
assembly scope.

## Synthetic evidence cannot authorize

Synthetic packets are accepted only to exercise the contract. A complete
synthetic owner approval can be `structurally_approvable`, but every authority
field remains false. This prevents test fixtures from becoming operational
receipts through copying, path changes, or optimistic interpretation.

The state boundary is:

| Evidence and decision | Structural result | Private assembly authority |
| --- | --- | --- |
| Public contract only | review packets may be prepared | false |
| Synthetic double approval + owner approval | contract path exercised | false |
| Real review with any rejection | role roster rejected | false |
| Real double approval + real owner approval | curator-only intake may begin | true |

The last row remains a structural authorization claim. The validator explicitly
does not authenticate the application owner, auditor, role holders, or source
appointment evidence.

## Fail-closed validation

Run:

```bash
scripts/check-engram-g1-role-review.sh

python3 scripts/eval/engram_g1_role_review.py validate-contract \
  --contract scripts/eval/fixtures/engram_g1_role_review_contract_v1.json

python3 scripts/eval/engram_g1_role_review.py validate-review \
  --contract scripts/eval/fixtures/engram_g1_role_review_contract_v1.json \
  --preflight-contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json \
  --review-packet data/eval/engram-g1/ROLE_REVIEW.private.json

python3 scripts/eval/engram_g1_role_review.py validate-owner-decision \
  --contract scripts/eval/fixtures/engram_g1_role_review_contract_v1.json \
  --preflight-contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json \
  --review-packet data/eval/engram-g1/ROLE_REVIEW.private.json \
  --owner-decision data/eval/engram-g1/OWNER_DECISION.private.json
```

The checker proves deterministic receipts and rejects contract relaxation,
forbidden owner overlap, false curator overlap, auditor overlap, chronology
errors, candidate authorship, unsalted commitments, raw identities, zero
receipts, role/review hash drift, approval after reviewer rejection, premature
owner decisions, owner mismatch, authorization-scope widening, real packets
outside ignored `data/`, and duplicate JSON fields.

No real role, review, or owner-decision packet is created by G1.2. The next
external action belongs to the application owner and an auditor outside the
five role holders. Until their consumer-owned evidence exists, private corpus
assembly authority remains false.
