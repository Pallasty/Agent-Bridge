# Engram G1.3 Structural Corpus-Freeze Review

Date: 2026-07-18

Status: **READY FOR STRUCTURAL FREEZE-REVIEW PACKETS / SECURE CUSTODY REQUIRED / NO AUTHORITY**

## Decision

G1.3 preregisters the corpus-freeze review before any private G1 corpus is
assembled. It fixes the manifest, reviewer, custody, redaction, and chronology
rules before reviewers can see a proposed cohort.

This gate is deliberately non-authorizing. It can validate a synthetic or
claimed-real packet chain and can report a structurally complete claimed-real
double endorsement. That result still requires preregistration of a separate
secure-custody and authenticated-authority adapter; it is not ready for
authenticated review. G1.3 never freezes a corpus and never opens
candidate-protocol preregistration.

The registered contract is
`scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json`,
SHA-256
`5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504`.
It binds two immutable predecessors:

- G1.1 freeze-preflight commit
  `3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`, contract SHA-256
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`,
  and validator SHA-256
  `f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`;
- hardened G1.2 role-review commit
  `400550236a643867086464e681be1fd5d12e579f`, contract SHA-256
  `f8c6cb0784b9981d5f9492bfa5d3539972e9eda2a0c28568ecda251c3f1c9e35`,
  and validator SHA-256
  `98c71e96cfc05552ed5fecfb92f74066d3e0ddab173015f64abede730545a3a6`.

## Exact input chain

One structural freeze review binds the exact bytes of:

1. the G1.1 role-commitment packet;
2. the G1.2 application-owner and independence-auditor review packet;
3. the G1.2 owner endorsement for later authentication;
4. the G1.1 30-group private manifest;
5. the G1.3 two-reviewer freeze packet.

All packets must carry the same evidence class. A claimed-real chain must remain
untracked under the canonical repository's ignored `data/` tree. Packet bytes
are read once for structural validation and every later stage binds their
SHA-256, but G1.3 does not securely capture or retain path identity.

Chronology is strict: role review follows appointment, owner endorsement follows
the completed review, manifest assembly follows the endorsement, and freeze
review follows manifest assembly. Equal timestamps are rejected.

The chronology check does not turn the G1.2 endorsement into assembly
permission. G1.2 keeps assembly authority false on every path. A claimed-real
manifest is therefore evidence presented for structural review, not proof that
its assembly was authorized. G1.3 cannot repair or legitimize an unauthorized
assembly.

## Manifest invariants

The exact G1.1 validator revalidates the manifest. It must contain 30 indivisible
episode groups with the registered FIT/development/sealed counts, signature
minimums, one FIT-only admitted G0 incident, two identical baseline replays, at
least four application families, and no family above 10 groups.

The proposed freeze object is the exact manifest bytes, not a mutable label or
database query. The structural endorsement permits no group addition, removal,
substitution, repartition, or relabeling. Any byte change requires a new review.
These invariants define a proposal only; `grants_corpus_freeze` is false.

## Two reviewers and sealed custody

The private packet uses schema
`agent_bridge.engram_g1_corpus_freeze_review_packet.v1` and contains exactly two
reviewer decisions. Their salted commitments must equal the two appointed
`freeze_reviewer` commitments, each exactly once.

Each endorsement attests that the reviewer checked:

- exact manifest-byte binding;
- roster and aggregate partition counts;
- provenance receipts and deterministic replay integrity;
- the application-family cap and admitted G0 FIT-only placement;
- candidate-exclusion rules;
- that sealed raw material was not received.

Both reviewers must endorse before the structural freeze endorsement is
complete. That completion is not submission readiness for authenticated review;
secure custody remains unverified. A rejection remains a valid structural
result and cannot open any later gate. Review receipts are non-placeholder and
distinct.

The custodian commitment must match the sole
`sealed_evaluator_custodian`. The custodian attests that the exact manifest and
private salts remain in custody, bytes did not change during review, reviewers
received hash-only material, and the candidate received neither the manifest
nor sealed material. The custody receipt is non-placeholder and distinct from
both review receipts.

The validator checks commitment relationships and packet structure. It cannot
authenticate a person, appointment, review act, receipt, custody claim, or
evidence truth.

## Zero-authority state machine

| State | Structural result | Freeze authority | G1.4 ready |
| --- | --- | ---: | ---: |
| Public contract only | packet preparation allowed | false | false |
| Synthetic double endorsement | contract path exercised | false | false |
| Claimed-real chain with a rejection | review rejected | false | false |
| Claimed-real double endorsement + custody claim | structural endorsement complete; secure custody required | false | false |

Every receipt keeps the following false:

- private-corpus assembly authority;
- G1 corpus-freeze authority;
- candidate manifest and FIT access;
- candidate implementation;
- BioCortex experiment execution;
- retrieval-order mutation;
- live-store writes;
- runtime promotion;
- candidate-protocol preregistration readiness.

The `consumer_owned_real` label, placement under ignored `data/`, complete
review flags, and successful local validation are caller-controlled structural
claims. None can mint authority. The checker proves this with a complete
synthetic chain relabeled as claimed-real under ignored `data/`; every authority
field remains false.

G1.3 does not implement no-follow, retained-identity file capture. Therefore a
caller-controlled claimed-real path can never produce an authenticated-review
readiness claim, even when every packet and custody attestation is structurally
consistent. The only permitted successor action is preregistration of the
separate secure-custody and authenticated-authority adapter.

## Future authenticated adapter

Any authority-bearing successor is a separate gate and requires its own
preregistration and threat review. At minimum it must verify domain-separated
signatures against independently configured owner, auditor, reviewer, and
custodian trust anchors; bind the canonical repository and predecessor commits;
walk private paths with no-follow directory descriptors; retain file identity
through validation; define a hardlink policy; and reject replay or scope drift.

No such adapter is implemented here. A G1.3 receipt is not admissible as secure
custody evidence by itself: the successor must securely reopen the originals,
retain their identity through revalidation, and prove that the authenticated
bytes match the structural bindings. G1.4 remains closed until authenticated
freeze authority exists through that separate mechanism.

## Redacted receipts

G1.3 freeze-review `packet_id` values are non-placeholder SHA-256 values, cannot
alias any SHA-256 value in the bound chain or current review packet, and are
omitted from receipts. Every other redacted SHA-256 value in the bound input
chain or freeze packet—including group, query, commitment, and private receipt
values—must not alias a public contract, validator, or whole-packet receipt
digest. Receipts contain public bindings and aggregate counts only. They omit
group identifiers, partition membership, holder and reviewer commitments,
appointment/review/custody receipts, raw identities, raw queries, and sealed
material.

## Run

```bash
scripts/check-engram-g1-corpus-freeze-review.sh

python3 scripts/eval/engram_g1_corpus_freeze_review.py validate-contract \
  --contract scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json

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

The checker builds the full 30-group synthetic chain and rejects contract
relaxation, owner rejection, pre-endorsement assembly, byte-binding drift,
reviewer impersonation or duplication, incomplete endorsements, placeholder or
duplicate receipts, custody mismatch, manifest drift, candidate involvement,
raw identity fields, non-opaque or aliasing packet identifiers, real packets
outside ignored `data/`, redacted SHA-256 values aliasing public contract,
validator, or packet digests, and duplicate JSON keys.

Its table-driven alias matrix covers chain packet IDs, holder commitments,
owner receipts, group IDs, query and target commitments, current review and
custody receipts, and the freeze packet ID. The target categories span public
contract, current and predecessor validator, and whole-packet digests. Each
case repairs all downstream byte bindings and must fail at the dedicated alias
guard.

The checker creates temporary synthetic packets relabeled claimed-real under
ignored `data/`, validates that laundering attempt, and removes them. In normal
use G1.3 can structurally read caller-supplied claimed-real packets, but it does
not authenticate their people, evidence, path custody, or authority. No
authenticated real-world evidence was used for this gate result.
