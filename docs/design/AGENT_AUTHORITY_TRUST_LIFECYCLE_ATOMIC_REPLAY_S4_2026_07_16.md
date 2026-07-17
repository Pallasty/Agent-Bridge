# Agent Authority Trust Lifecycle And Atomic Replay S4

Date: 2026-07-16

Status: DESIGN_FROZEN / OFFLINE_SIGNED_LIFECYCLE / PURE_REPLAY_CAS / NO_RUNTIME_AUTHORITY

## Decision

S4 adds two offline reference models above S3:

1. a signed trust-registry lifecycle journal under a frozen evaluator-owned
   public root anchor; and
2. a pure compare-and-swap model for atomic replay consumption over a versioned
   read-only snapshot.

S4 computes candidate state and review evidence in memory. It does not write a
registry, nonce ledger, database, memory, graph, session, MCP service, or T6
runtime. It does not create an authorization layer between trusted agents.

## What S4 Advances

S3 proved that canonical authority receipts can be verified with a separated
public-test trust registry and real Ed25519 verification. It consumed only a
static revocation/replay snapshot.

S4 tests the next protocol questions:

- can a signed lifecycle journal reject rollback, fork, tamper, unauthorized
  signers, invalid transitions, overlap, resurrection, and stale activation;
- can a pure versioned transaction model give exactly one winner, idempotent
  retry, and explicit crash-window behavior without mutating live state;
- can both models remain review-only and preserve every runtime nonclaim.

S4 does not prove root-of-root rotation, custody, HSM/KMS behavior, threshold
authorization, real database isolation, durability, linearizability, crash
recovery, or distributed consensus.

## Source Lineage

- latest master ancestor:
  `c9c50917687c7715b031a6bfe8dd7801bfd737ee`
- S3 result:
  `149bafbc3a04126ea28f05a85c3e30d2748aceed`
- S4 lineage merge:
  `72ba3dabd2569e651e05a90dfc1c898fa366c24e`
- S3 verifier SHA-256:
  `b845f23afddb48e0b5a60f90fc6317e79f0e8495914e4634281a315c3e1d0d19`
- S3 trust registry SHA-256:
  `1e26edf7a5c71ac972d5c1c7e2496d8c1baa772d9571db995cfac04fe6c3d573`
- S3 signed receipts SHA-256:
  `1a15620e6dc16166d71b4458d5207eacf30579b8f631c48f85ac62fba2456d8d`
- S3 design SHA-256:
  `2ad2bb8d8e1bb64db80344c898754f600cfccb82cc29944146221754e61a2839`
- S3 result SHA-256:
  `fd6fe75e56ffddc64f209e3ad822186a03f618084e858892cfc15bd6cc7539fd`

## Frozen Inputs

Evaluator root anchor:

    crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_anchor_s4.json

SHA-256:

    daae7bea20842cd1f8116084f757843dcc9020aa2b3d40ab26ce3af9114f1fe5

Signed lifecycle journals:

    crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_journals_s4.json

SHA-256:

    b1ffd8c38060f6f39925fea97ac3c21f20a138ea1debb430c06f9fa44b7c4342

Atomic replay schedules:

    crates/bridge/tests/fixtures/agent_authority_atomic_replay_schedules_s4.json

SHA-256:

    dd24e1a8678205ce4f7ae6bae940eeb1e75136f7614b425b7989abe4e0d908d3

The anchor is evaluator-owned. The journal and replay files are frozen test
corpora. Expected statuses, reasons, and outcomes are comparison data only.

## Test Key Provenance

The anchor contains three public Ed25519 keys from RFC 8032 section 7.1 test
vectors: an active lifecycle authority, an active audit-only signer, and a
revoked lifecycle authority. Lifecycle event signatures were precomputed with
OpenSSL 3.5.5 using the corresponding published test seeds.

The seeds are public test data. They are not committed to the fixtures or
embedded in the verifier. The checker performs verification only with the
existing dev-only ring 0.17.14 dependency inherited from S3.

## Trust Partition

The root anchor fixes:

- root id and trusted root epoch;
- minimum accepted registry generation;
- genesis digest;
- event schema and Ed25519 algorithm;
- required lifecycle-authority role;
- public signer keys and revocation state;
- exact S3 source and commit pins.

The anchor explicitly says that it is a fixture, contains no private key, is
not a production trust root, and does not prove root rotation.

Each lifecycle case carries a trusted checkpoint plus a presented signed
journal. Scenario-specific checkpoints are evaluator-owned test inputs; they
are not Agent-supplied production checkpoints.

## Signed Lifecycle Event

Every signature binds these 15 ordered, typed, length-bound fields:

1. event schema;
2. root id;
3. root epoch;
4. registry generation;
5. sequence;
6. previous-event digest;
7. action;
8. target key id;
9. replaced key id;
10. target not-before time;
11. target not-after time;
12. effective time;
13. reason code;
14. signer id;
15. algorithm.

The canonical domain is:

    agent_bridge.authority_trust_lifecycle.s4.event.v0

The event digest is SHA-256 over canonical bytes. ring verifies Ed25519 over
those same bytes directly. The declared event digest is never used as the
signature message.

## Lifecycle State Machine

The key states are:

    absent -> registered -> active -> rotated_out
                            |            |
                            v            v
                         compromised   revoked
                            \            /
                             -> retired <-

Allowed actions are register, activate, rotate, revoke, quarantine, and
retire. Rotation activates a registered successor and references the active or
compromised predecessor. Revoked, compromised, and retired states cannot be
resurrected. At most one key may be active.

Activation and rotation are valid at exact not-before and not-after
boundaries. The active key must also be valid at checkpoint evaluation time.

## Lifecycle Precedence

The evaluator derives exactly one status in this order:

1. unavailable when independent verification is unavailable;
2. untrusted for root-id mismatch or a future unanchored root epoch;
3. rollback for an older root epoch or registry generation;
4. forked for sequence, previous-digest, or checkpoint-head divergence;
5. invalid for digest, encoding, signature, metadata, or transition failure;
6. untrusted for unknown signer, algorithm, or role mismatch;
7. revoked for a valid signature from a revoked signer or attempted key
   resurrection;
8. stale for activation/current-key validity failure;
9. ambiguous for multiple active keys;
10. current otherwise.

Checks within a status emit deterministic lexical reasons.

## Frozen Lifecycle Distribution

The corpus contains 21 cases and 190 signed event instances.

| Status | Count |
|---|---:|
| current | 2 |
| invalid | 3 |
| untrusted | 3 |
| rollback | 2 |
| forked | 5 |
| revoked | 2 |
| stale | 2 |
| ambiguous | 1 |
| unavailable | 1 |
| total | 21 |

The two controls cover the baseline recovery chain and an exact not-after
rotation boundary. Adversarial cases cover epoch/generation rollback, sequence
gap/duplicate/reorder, previous-digest fork, checkpoint mismatch, digest and
signature tamper, signer role/revocation, invalid transition, overlap,
resurrection, activation validity, root mismatch, and verifier availability.

## Atomic Replay Model

Each replay schedule starts from the same immutable version-41 snapshot with
one committed record. A step supplies a synthetic receipt id and nonce, a
source-bound S3 case id, transaction id, expected version, and one mode:

- commit;
- prepare_only;
- crash_before_commit;
- commit_ack_lost.

The transaction order is:

1. require lifecycle status current;
2. require the referenced S3 source case status verified;
3. resolve an exact idempotent committed transaction before version checking;
4. reject a consumed nonce or reused transaction identity;
5. require expected version to equal candidate version;
6. return prepare/crash evidence without changing candidate state, or atomically
   clone, increment version, and add one consumed record;
7. expose candidate state as report data only.

This is a reference transition function. It does not reserve or commit in a
real store.

## Frozen Replay Outcomes

There are 26 schedules and 30 deterministic steps.

| Outcome | Count |
|---|---:|
| committed | 4 |
| already_committed | 3 |
| nonce_replayed | 3 |
| version_conflict | 1 |
| prepared_not_committed | 1 |
| crashed_before_commit | 1 |
| commit_ack_lost | 1 |
| transaction_identity_conflict | 1 |
| receipt_ineligible | 7 |
| lifecycle_blocked | 8 |
| total | 30 |

Exactly seven steps may set `reviewable_after_atomic_consume=true`: four
acknowledged commits and three idempotently confirmed commits. A lost commit
acknowledgement is not reviewable until retry confirms the committed record.

Two forward and reverse schedules model competing synthetic receipts sharing a
nonce. Exactly one commits in each schedule. The order is deterministic and no
claim is made about scheduler fairness.

## S3 Composition Boundary

Replay schedules reference case ids from the frozen S3 signed-receipt corpus.
The S4 evaluator pins that corpus and uses the S3 case status established by the
separately verified S3 result. It does not re-run the complete S3 receipt
verifier or prove that each synthetic replay receipt id/nonce is an end-to-end
signed S3 receipt.

Accordingly, every report keeps
`receipt_identity_end_to_end_reverified=false`. End-to-end verifier composition
is a later gate, not an S4 claim.

## T6 Review Preview

A step is reviewable only after current lifecycle, S3-verified eligibility,
and acknowledged or idempotently confirmed atomic consumption.

Every report keeps these false:

- may_dispatch;
- may_run_shadow;
- may_enable_runtime;
- may_run_executor;
- may_write_memory;
- may_write_graph;
- may_change_retrieval;
- may_change_session;
- may_persist_replay_state;
- may_mutate_trust_registry;
- production_trust_root_proven;
- root_rotation_proven;
- production_atomicity_proven;
- production_authority_granted.

## Pass Meaning

A pass proves deterministic offline behavior for the frozen public-test anchor,
signed journals, and pure replay schedules. It proves no production root,
credential custody, live transaction isolation, durable replay protection,
runtime safety, or execution authority.

Any end-to-end S3/S4 composition, real transactional adapter, root rotation,
runtime consumer, deployment, or authority grant is a separate owner gate.
