# Agent Authority Trust Lifecycle And Atomic Replay S4 Preregistration

Date: 2026-07-16

Status: PREREGISTERED / OFFLINE_SIGNED_LIFECYCLE / PURE_REPLAY_CAS / NO_RUNTIME_AUTHORITY

## Question

Can a source-bound offline evaluator reject signed trust-lifecycle rollback,
fork, tamper, unauthorized transitions, overlap, resurrection, and stale
activation, while a separate pure CAS model gives deterministic single-winner,
idempotency, and crash-window behavior without persisting any state or gaining
runtime authority?

## Frozen Inputs

- design:
  `docs/design/AGENT_AUTHORITY_TRUST_LIFECYCLE_ATOMIC_REPLAY_S4_2026_07_16.md`
- root anchor:
  `crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_anchor_s4.json`
- signed lifecycle journals:
  `crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_journals_s4.json`
- atomic replay schedules:
  `crates/bridge/tests/fixtures/agent_authority_atomic_replay_schedules_s4.json`
- checker:
  `crates/bridge/examples/agent_authority_trust_lifecycle_atomic_replay_s4.rs`
- S3 verifier, trust registry, signed corpus, design, and result.

Frozen fixture hashes:

- root anchor:
  `daae7bea20842cd1f8116084f757843dcc9020aa2b3d40ab26ce3af9114f1fe5`
- signed lifecycle journals:
  `b1ffd8c38060f6f39925fea97ac3c21f20a138ea1debb430c06f9fa44b7c4342`
- atomic replay schedules:
  `dd24e1a8678205ce4f7ae6bae940eeb1e75136f7614b425b7989abe4e0d908d3`

Frozen lineage:

- latest master: `c9c50917687c7715b031a6bfe8dd7801bfd737ee`
- S3 result: `149bafbc3a04126ea28f05a85c3e30d2748aceed`
- S4 lineage merge: `72ba3dabd2569e651e05a90dfc1c898fa366c24e`

## Frozen Lifecycle Distribution

- total cases: 21;
- signed event instances: 190;
- current controls: 2;
- invalid: 3;
- untrusted: 3;
- rollback: 2;
- forked: 5;
- revoked: 2;
- stale: 2;
- ambiguous: 1;
- unavailable: 1.

Every non-control must fail closed and neither expected status nor expected
reason may influence derivation.

## Frozen Replay Distribution

- schedules: 26;
- steps: 30;
- committed: 4;
- already_committed: 3;
- nonce_replayed: 3;
- version_conflict: 1;
- prepared_not_committed: 1;
- crashed_before_commit: 1;
- commit_ack_lost: 1;
- transaction_identity_conflict: 1;
- receipt_ineligible: 7;
- lifecycle_blocked: 8.

Exactly seven steps are reviewable: acknowledged commits and exact idempotent
confirmations only. Every other outcome must remain non-reviewable.

## Frozen Lifecycle Precedence

1. verifier availability;
2. root id and root epoch;
3. minimum registry generation;
4. sequence, previous digest, and checkpoint head;
5. event digest and encoding;
6. signer lookup, algorithm, and role;
7. ring Ed25519 verification;
8. signer revocation;
9. lifecycle transition, resurrection, validity, and active-key uniqueness;
10. current.

## Frozen Replay Precedence

1. lifecycle currentness;
2. source-bound S3 status verified;
3. exact committed idempotency;
4. consumed nonce;
5. reused transaction identity;
6. expected-version CAS;
7. prepare/crash behavior or candidate commit;
8. reviewability.

## Required Tests

1. exact 21-case lifecycle distribution and lexical reasons;
2. exact 26-schedule, 30-step replay outcomes and seven reviewable steps;
3. zero adversarial lifecycle-current results and zero control false rejects;
4. exactly one commit in both forward/reverse competing schedules;
5. expected lifecycle/replay labels cannot change derived output;
6. all 15 signed event fields change canonical bytes;
7. digest and signature tamper fail the real ring path;
8. unknown, wrong-role, and revoked signers fail closed at their frozen stage;
9. rollback, fork, overlap, resurrection, and activation boundaries are exact;
10. stale source pins, malformed public keys, duplicate ids, malformed journals,
    invalid snapshots, duplicate nonce/transaction records, and unsorted reasons
    fail input validation;
11. lifecycle fixtures, replay snapshot, and schedules remain immutable;
12. reports are structurally equal and byte-identical across runs;
13. all authority, persistence, production-root, production-atomicity, runtime,
    and end-to-end receipt-composition nonclaims remain explicit and false.

## TDD Gate

The checker test skeleton must compile-fail on missing anchor/journal/replay
types, canonicalization, signature verification, lifecycle state machine,
snapshot digest, CAS transition, suite evaluation, and report APIs before the
minimal implementation is added.

## Pass Meaning

A pass proves only the frozen offline reference behavior. It does not prove:

- production root authenticity, custody, rotation, compromise recovery, KMS,
  HSM, threshold signing, or network identity;
- end-to-end S3 receipt identity/nonce composition in the replay schedules;
- real database isolation, durability, linearizability, crash recovery, or
  distributed consensus;
- live replay prevention, T6/runtime safety, deployment readiness, or execution
  authority.

## Prohibited Actions

- no production/private credential or key;
- no committed signer or signing service;
- no KMS/HSM, secret store, or network identity provider;
- no live database, nonce ledger, registry, memory, graph, or session mutation;
- no MCP/T6 runtime consumer;
- no shadow/executor execution or runtime enablement;
- no deploy, authority grant, master merge, or production-security claim.
