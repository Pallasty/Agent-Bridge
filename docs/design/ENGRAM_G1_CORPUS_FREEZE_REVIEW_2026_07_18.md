# Engram G1.3 Corpus-Freeze Review

Date: 2026-07-18

Status: **READY FOR PRIVATE FREEZE-REVIEW PACKETS / NO CURRENT AUTHORITY**

## Decision

G1.3 preregisters the corpus-freeze review before any private G1 corpus is
assembled. This prevents the roster, partition, provenance, replay, or custody
rules from being relaxed after reviewers have seen the proposed cohort.

The registered public contract is
`scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json`,
SHA-256
`885ad2c0a0590631b1a4c33e168bffd5e1153039a1b5325a24c343599c5c35b5`.
It binds two immutable predecessors:

- G1.1 freeze preflight commit
  `3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`, contract SHA-256
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`,
  and validator SHA-256
  `f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`;
- G1.2 role-review commit
  `426560f67369ec5851b4813fe31a3fe12ae4adde`, contract SHA-256
  `efb7464e2922d0dd2645698435272714316d07f786bd5a56114e900b99e31f6c`,
  and validator SHA-256
  `5efe72815341492b84a4bd0dee487d1eb572e60e7938f3df7e5cb9710ef8706f`.

This public contract does not observe role evidence, assemble or freeze a
corpus, or grant candidate access. It fixes only the later private review
protocol.

## Exact input chain

One freeze decision binds the exact bytes of:

1. the G1.1 role-commitment packet;
2. the G1.2 application-owner and independence-auditor review packet;
3. the G1.2 owner decision approving private corpus assembly;
4. the G1.1 30-group private manifest;
5. the G1.3 two-reviewer freeze packet.

All packets must carry the same evidence class. A real chain must remain
untracked under the repository's ignored `data/` tree.

Chronology is fail-closed. The role review follows appointment, the owner
decision follows the completed role review, manifest assembly follows the
owner decision, and freeze review follows manifest assembly. Equal timestamps
are rejected at every strict transition.

A manifest assembled before owner authorization cannot be repaired by adding
an approval later. It must be discarded and assembled again under an approved
chain.

## Manifest invariants

The manifest is revalidated by the exact G1.1 validator before freeze review.
It must contain exactly 30 indivisible episode groups with the registered
FIT/development/sealed counts, signature minima, one FIT-only admitted G0
incident, two identical baseline replays, at least four application families,
and no family above 10 groups.

The freeze object is the exact manifest bytes, not a logical label or mutable
database query. An approved freeze permits no group addition, removal,
substitution, repartition, or relabeling. Any byte-level manifest change
requires a new freeze review.

## Two independent freeze reviewers

The private packet uses schema
`agent_bridge.engram_g1_corpus_freeze_review_packet.v1`. It must contain
exactly two reviewer decisions. Their salted commitments must equal the two
`freeze_reviewer` commitments in the bound role packet, each exactly once.

Each approval attests that the reviewer checked:

- the exact manifest-byte binding;
- roster and aggregate partition counts;
- provenance receipts;
- deterministic replay integrity;
- the application-family cap;
- the admitted G0 incident's FIT-only placement;
- candidate-exclusion rules;
- that the reviewer did not receive sealed raw material.

Both reviewers must approve. A rejection is a valid structural result but
produces no freeze authority. Review receipts must be non-placeholder and
distinct.

## Sealed custody

The custodian commitment must exactly match the sole
`sealed_evaluator_custodian` in the role packet. The custodian attests that:

- the exact manifest and private salts remain in custody;
- manifest bytes did not change during review;
- freeze reviewers received hash-only material;
- the candidate received neither manifest nor sealed material;
- sealed raw material, partition membership, and labels remain undisclosed;
- freeze reviewers did not receive sealed raw material.

The validator checks commitment relationships and packet structure. It cannot
authenticate a person, appointment, review act, receipt, or custody claim.
The custody receipt must be non-placeholder and distinct from both freeze-
review receipts.

## Synthetic and real authority

Synthetic packets exercise the complete chain but always emit zero authority.
Even a two-approval synthetic packet returns
`SYNTHETIC_FREEZE_APPROVAL_VALID_NO_AUTHORITY`.

Only a structurally valid `consumer_owned_real` chain with prior real assembly
authorization, a valid manifest, two freeze approvals, and matching custody can
return `G1_CORPUS_FREEZE_AUTHORIZED_FOR_EXACT_MANIFEST`.

That narrow result authorizes only recording the exact manifest hash as the G1
freeze and preparing the next candidate-protocol preregistration. It does not
give the candidate the manifest, FIT material, or sealed material. It does not
authorize candidate implementation, BioCortex execution, retrieval-order
mutation, live-store writes, or runtime promotion.

| State | Structural result | G1 freeze authority | Candidate implementation |
| --- | --- | ---: | ---: |
| Public contract only | private review may be prepared | false | false |
| Synthetic full approval | contract path exercised | false | false |
| Real chain with either rejection | freeze rejected | false | false |
| Real double approval + custody | exact manifest may be frozen | true | false |

## Redacted receipts

Receipts contain whole-packet hashes and aggregate counts only. They omit group
identifiers, partition membership, holder and reviewer commitments,
appointment/review/custody receipts, raw identities, raw queries, and sealed
material.

## Run

```bash
scripts/check-engram-g1-corpus-freeze-review.sh

python3 scripts/eval/engram_g1_corpus_freeze_review.py validate-contract \
  --contract scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json

python3 scripts/eval/engram_g1_corpus_freeze_review.py validate-chain \
  --contract scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json \
  --preflight-contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-review-contract scripts/eval/fixtures/engram_g1_role_review_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json \
  --role-review-packet data/eval/engram-g1/ROLE_REVIEW.private.json \
  --owner-decision data/eval/engram-g1/OWNER_DECISION.private.json \
  --manifest data/eval/engram-g1/CORPUS_MANIFEST.private.json

python3 scripts/eval/engram_g1_corpus_freeze_review.py validate-freeze-review \
  --contract scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json \
  --preflight-contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-review-contract scripts/eval/fixtures/engram_g1_role_review_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json \
  --role-review-packet data/eval/engram-g1/ROLE_REVIEW.private.json \
  --owner-decision data/eval/engram-g1/OWNER_DECISION.private.json \
  --manifest data/eval/engram-g1/CORPUS_MANIFEST.private.json \
  --freeze-review data/eval/engram-g1/CORPUS_FREEZE_REVIEW.private.json
```

The checker builds the full 30-group synthetic chain in a temporary directory
and rejects contract relaxation, owner rejection, pre-authorization assembly,
byte-binding drift, reviewer impersonation or duplication, incomplete
approval, placeholder or duplicate receipts, custody mismatch, manifest drift,
candidate involvement, raw identity fields, real packets outside ignored
`data/`, and duplicate JSON keys.

No real role, review, owner-decision, manifest, or freeze packet is created by
G1.3. Until that external evidence exists, current freeze authority remains
false.
