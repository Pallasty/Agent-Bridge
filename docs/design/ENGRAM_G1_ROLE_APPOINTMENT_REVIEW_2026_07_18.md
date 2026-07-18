# Engram G1.2 Role-Appointment Review

Date: 2026-07-18

Status: **READY FOR PRIVATE ROLE REVIEW PACKETS / AUTHENTICATION REQUIRED / NO AUTHORITY**

## Decision

G1.2 inserts an independently reviewable structural review chain between the
G1.1 role-commitment packet and any future private grouped-corpus assembly. A
role roster is not self-authorizing: an application owner and an independence
auditor must review the exact role-packet bytes, and the application owner must
then issue a separate endorsement bound to the completed review bytes.

The registered public contract is
`scripts/eval/fixtures/engram_g1_role_review_contract_v1.json`, SHA-256
`842a86010b61a030993d37e6cc2b06206315a22a5b319c79dfaf07ed32522c09`.
It binds G1.1 commit
`3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`, contract SHA-256
`5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`,
and validator SHA-256
`f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`.

This public contract does not observe appointment evidence, assign real people,
or authorize assembly. It defines only the next fail-closed review protocol.
No self-declared evidence class, ignored path, hash-shaped value, or successful
local validation can produce assembly authority.

## Structural review chain

The chain has four distinct records:

1. the G1.1 role packet appoints one candidate implementer, one consumer
   curator, two freeze reviewers, and one sealed evaluator/custodian;
2. the application-owner review checks appointment completeness, consumer
   ownership, and authority to run this workflow;
3. an independence auditor checks holder separation, owner overlap, candidate
   exclusions, sealed custody, salt custody, and appointment chronology;
4. the application owner issues a separate endorse-or-reject decision after
   both reviews are complete.

The candidate implementer cannot author or approve either review, issue the
owner decision, assemble the private corpus, inspect the private manifest, or
receive sealed material.

## Reviewer separation

Reviewer identities are represented only by privately salted SHA-256
commitments. Raw names, handles, contact data, and identity fields are
forbidden. Review `packet_id` and owner `decision_id` values must also be
non-placeholder SHA-256 identifiers, so redacted receipts cannot echo a
human-readable identity hidden inside an otherwise generic identifier field.
An identifier must also differ from every holder, reviewer, appointment,
review, audit, and endorsement commitment in its packet lineage. Those
identifiers remain private and are omitted from redacted receipts.

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

Both reviewers must approve before an owner may endorse the bounded assembly
proposal for later authentication. A reviewer rejection is itself a valid
structural result, but it cannot be converted into an endorsement. The owner
may only record `reject_role_roster` for that chain.

A redacted review receipt contains decisions and hashes of whole packets. It
does not contain holder commitments, reviewer commitments, appointment
receipts, review receipts, raw identities, or raw corpus material. A valid
review packet still grants no authority.

## Private owner-decision packet

Actual decisions use schema
`agent_bridge.engram_g1_role_owner_decision_packet.v1`. They bind the exact
role and review packet bytes, repeat the application-owner commitment from the
review, occur strictly after review completion, and carry a non-placeholder
endorsement-receipt commitment.

The only decisions are:

- `endorse_private_corpus_assembly_for_authentication` after both reviews
  approve; or
- `reject_role_roster`.

A proposed scope must exactly match the public contract. It cannot be widened
inside a private packet, and structural validation never authorizes it.

## Exact proposed scope

A structurally valid chain may propose only the following for a later,
authenticated authority review:

- the consumer curator may create a private intake under ignored `data/`;
- the sealed evaluator/custodian retains custody;
- the curator may perform read-only baseline replay on disposable snapshots;
- the curator may prepare a hash-only manifest for later freeze review;
- intake is capped at 36 episode groups.

The proposal itself authorizes none of those actions. It also cannot freeze the
corpus, authorize candidate implementation, execute BioCortex, mutate retrieval
order, write live state, or promote runtime. The candidate lane may not execute
the proposed scope.

## Synthetic evidence cannot authorize

Synthetic packets are accepted only to exercise the contract. A complete
synthetic endorsement can be structurally valid, but every authority field
remains false. A chain labeled `consumer_owned_real` is likewise only a claim:
it may advance to authenticated authority review, never directly to assembly.

The state boundary is:

| Evidence and decision | Structural result | Private assembly authority |
| --- | --- | --- |
| Public contract only | review packets may be prepared | false |
| Synthetic double approval + owner endorsement | contract path exercised | false |
| Real review with any rejection | role roster rejected | false |
| Claimed-real double approval + owner endorsement | ready for authentication | false |

The validator explicitly does not authenticate the application owner, auditor,
role holders, or source appointment evidence. A later adapter must verify
domain-separated signatures against independently configured trust anchors
before any assembly authority can become true.

The current ignored-path check is likewise structural, not a custody proof.
The reader captures stable bytes before a later pathname privacy check; a
future authority-bearing adapter must instead anchor the canonical repository,
walk the private path with no-follow directory descriptors, retain the same
file identity through validation, and define a hardlink policy. Until then,
foreign-repository copies and pathname races cannot gain authority because this
validator has no authority-producing state.

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
receipts, human-readable or private-commitment-aliasing packet identifiers,
role/review hash drift,
endorsement after reviewer rejection, premature owner decisions, owner
mismatch, proposed-scope widening, synthetic-to-real relabeling as an authority
escalation, real packets outside ignored `data/`, and duplicate JSON fields.

No real role, review, or owner-decision packet is created by G1.2. The next
external action belongs to the application owner and an auditor outside the
five role holders. Even after their consumer-owned evidence exists, private
corpus assembly authority remains false until a separately registered,
authenticated authority verifier accepts the chain.
