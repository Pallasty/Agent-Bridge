# Memory Temporal Atomic Authority Operation S11

Date: 2026-07-14

Status:
`ATOMIC_AUTHORITY_OPERATION_OUTBOX_PREREGISTERED_SYNTHETIC_DB_ONLY_DB_KMS_NON_ATOMIC_EXACTLY_ONCE_UNPROVED_NO_PROVIDER_NO_CUSTODIAN_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Purpose

S10 froze a lookup-only protocol for an already submitted S9 operation, but it
did not define how an authority-operation journal atomically registers that
operation, consumes the concrete replay identity, freezes one decision
commitment and signing message, and later stores a signature. S11 freezes that
missing operation/outbox sequence as a private synthetic model. It does not
derive, parse, or independently reverify raw S9 decision bytes.

The default-off Store feature is
`temporal-evidence-s11-atomic-authority-operation-synthetic`. It depends on
S10 and adds the private module
`crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs`.
There is no network client, database driver, KMS client, production provider,
production custodian, credential, public constructor, `StateStore` method,
Bridge feature forwarding, Bridge caller, BioCortex runtime influence, or
transport.

S11 is a protocol and fault-sequence preregistration. Its synthetic database
does not establish process-crash durability, database linearizability,
rollback resistance, split-brain fencing, signer non-equivocation, KMS
custody, or owner authorization.

## Frozen predecessor

S11 begins from the integrated S10 commit
`0dad535e2cfd1a911c139d053409e0c02a7a8a0c`; the S10 feature commit is
`4bc142e6182be4fa66a7b1542535314490dc714c`. The following S10 artifacts are
the frozen semantic predecessor:

- S10 contract:
  `da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88`;
- S10 successor gate:
  `9bedb7ef289f31a6b9409875d3b8e6fb3b4784aa972a329de229565caa5b1eb7`;
- S10 Rust source:
  `850ddf4c47c76e9008671d44c47ba944b384744a4c50640e134e6c24008d90e4`.

The machine-readable S11 contract is
`docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json`.
The successor gate is
`docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json`.

## Two persistent states

S11 permits exactly two persisted operation states:

```text
ABSENT
  -- L1: one atomic database transaction -->
DECISION_COMMITTED_UNSIGNED
  -- exact-version sign, verify, L2 CAS -->
SIGNED_COMMITTED
```

`ABSENT` is the absence of a record, not a third persisted state.
`SIGNATURE_OBSERVED` is only a volatile fault cut after a signer response and
before L2; it is not a persisted state. There is no durable `SIGNING`, lease,
timeout-expired, retryable-failed, or locally admitted state. Contradictory or
structurally impossible records produce `CONFLICT` or `INDETERMINATE` and must
be quarantined; quarantine is an operational response, not a repair transition
or a third operation state.

The only legal monotonic transition is
`DECISION_COMMITTED_UNSIGNED -> SIGNED_COMMITTED`. No field frozen at L1 may
change at L2. `SIGNED_COMMITTED` never regresses, expires, rotates to a new
signer, or returns to `DECISION_COMMITTED_UNSIGNED` or `ABSENT`.

The executable lookup API has three typed success outcomes:

- no exact operation record: `NOT_FOUND`;
- exact `DECISION_COMMITTED_UNSIGNED`: `PENDING(L1_WITNESS)`, with no recovery
  observation;
- exact `SIGNED_COMMITTED`: `COMMITTED(SYNTHETIC_RECORD)`, still only private
  non-admission sequence evidence.

Operation, request, challenge, replay identity, or immutable-field mismatch is
a fail-closed conflict error. Corruption, an exact retained witness becoming
absent, ambiguous storage, rollback, or an unavailable authoritative read is a
fail-closed indeterminate error. These errors correspond to S10 `CONFLICT` and
`INDETERMINATE`; they are not additional persistent states.

`begin_exact_once` is create-only. An ambiguous L1 acknowledgement must be
recovered with `lookup_exact`. `PENDING` returns a typed L1 witness binding the
operation, request, generation, L1 record, sign job, stable result, revision,
and sequence. Only `resume_exact_from_l1` with that exact witness may continue
the signing path. A retained witness followed by `NOT_FOUND`, or a different
witness at `PENDING`/`COMMITTED`, fails closed rather than recreating L1.

## L1: atomic database preparation

L1 is modeled by one critical section over the shared synthetic journal, with
no external call or other nontransactional side effect. Inside the same lock,
the model first requires the request to equal journal-owned provider cluster,
incarnation, generation, authority-snapshot commitment, canonical-decision
commitment, trust-policy commitment, signer ID, and exact signer version. It
then atomically:

1. reserve one scoped operation ID;
2. reserve one scoped nonzero S9 challenge;
3. consume one exact concrete replay identity;
4. reject the journal's modeled revoked state before the commit;
5. freeze the exact S9 request digest plus the already journal-owned authority
   snapshot and canonical-decision commitments;
6. freeze provider cluster, incarnation, journal generation, leader term,
   operation commit revision, and record sequence;
7. freeze the signer key ID and exact nonzero key version;
8. freeze a domain-separated sign-job ID and exact framed L1 decision message;
   and
9. write the `DECISION_COMMITTED_UNSIGNED` outbox record.

The synthetic journal does not derive a real S9 decision from authoritative
production state. The caller supplies opaque snapshot/decision digests, and L1
only accepts them when they equal the journal-owned synthetic commitments.
This establishes binding within one in-process sequence model, not real
currentness or an independent S9 decision verification.

The operation ID, challenge, and concrete replay identity have separate unique
constraints in their exact authority/tenant scope. An L1 abort leaves all of
them absent; an L1 commit retains all of them. In particular, a committed
`DECISION_COMMITTED_UNSIGNED` record permanently retains the consumed challenge and replay
identity even if the signer is unavailable forever. Timeout cannot reclaim
either identity.

A database library may internally rerun a pure L1 transaction body only when
that body contains no KMS, network, clock, callback, or other external side
effect. This is distinct from resubmitting the S9 operation. After an ambiguous
commit acknowledgement, the adapter must first perform an authoritative exact
lookup; it must not blind-submit the original S9 request.

## L2: exact sign and atomic finalization

Only an exact `DECISION_COMMITTED_UNSIGNED` record may drive signing. Every resume uses the same
sign-job ID, exact canonical message bytes, message digest, signer key ID, and
exact key version. It may not recompute the decision from current mutable
state, select the latest key version, substitute a new key after rotation, or
repeat L1.

The executable synthetic signer response contains only signer key ID, exact key
version, exact message digest, and Ed25519 signature. The model rejects a
mismatch in any of those fields and verifies the signature over the frozen L1
message under the independently supplied test permit.

It does not model Cloud KMS response names, CRC32C fields, protection level,
Transit response prefixes, authenticated transport, or provider-specific
attestation. Checking those fields remains a requirement for a future concrete
adapter, not S11 executable evidence. In such an adapter, the response remains
untrusted until it verifies:

- the response names the expected exact key version and required protection
  profile;
- request/response integrity metadata required by the provider is valid;
- the signature authenticates the exact frozen message under the independently
  pinned public key; and
- no response field changes the frozen operation identity or decision.

L2 is a second synthetic-journal critical section. It compare-and-swaps the exact
`DECISION_COMMITTED_UNSIGNED` record and atomically persists the verified
signature, a local L2 revision, a public deterministic row checksum, and state
`SIGNED_COMMITTED`. A CAS that finds an identical already committed record is
idempotent success. A different signature, decision, key version, generation,
term, revision, or sequence is a conflict and must not be overwritten.

Ed25519 authenticates only the exact frozen L1 decision message. The synthetic
L2 revision and checksum are not in that signed message; the checksum is
publicly recomputable and authenticates neither journal persistence nor a
database commit. The verified private observation intentionally excludes the
L2 revision and checksum. `SIGNED_COMMITTED` therefore means only that the
shared in-process journal currently contains that modeled state. It is not a
portable authenticated database-persistence receipt.

The stable result identity binds only immutable L1 metadata. It does not bind
the unauthenticated L2 revision or a later lookup revision. Exact duplicate
lookup or delivery of a `SIGNED_COMMITTED` record returns the stored synthetic
record without journal mutation.

## Exact resume and re-sign boundary

Cloud KMS and OpenBao signing calls do not share the database transaction. A
signer timeout can mean that no signature was produced or that a signature was
produced and its response was lost. S11 therefore permits only this narrow
recovery action:

```text
read exact DECISION_COMMITTED_UNSIGNED
  -> sign the same bytes with the same exact key version
  -> verify locally -> L2 exact CAS
```

This is an exact re-sign/resume, not a second authority decision and not a
second replay consume. It proves neither that the signer executed once nor
that only one valid signature was ever produced. If modeled L2 is already
committed, recovery returns the stored synthetic record rather than calling the
signer again.

An invalid signature, wrong key/version, different signature observed for the
same frozen job in the one shared journal, different decision for the same
operation, or impossible partial `SIGNED_COMMITTED` record fails closed. The
synthetic implementation detects some same-journal conflicts; it does not
implement a production quarantine service or prove that all branches and
signer responses were observed. No failure may be silently repaired by
changing the signer or rewriting history.

## Invariants and threat response

The frozen invariants are:

1. **Exact identity:** one operation ID binds one exact request, challenge,
   replay identity, decision, sign job, provider identity, and signer version.
2. **Unique consume:** a challenge or concrete replay identity cannot be
   consumed by another operation in the same authority scope.
3. **Decision immutability:** the decision and sign message are fixed at L1 and
   are never recomputed during recovery.
4. **Monotonic persistence:** only
   `DECISION_COMMITTED_UNSIGNED -> SIGNED_COMMITTED` is legal; all regressions
   and partial states fail closed.
5. **Synthetic commit completeness:** only a locally verified L1 signature
   stored by the modeled L2 CAS can produce the typed `COMMITTED` lookup
   outcome in this shared journal. Neither the signature nor the public L2
   checksum proves an external database commit.
6. **No timeout release:** an unresolved signer or database result never
   releases an identity, authorizes local fallback, or creates an observation.
7. **Exact duplicate semantics:** an exact duplicate sees the existing state;
   it does not consume, decide, or sign as a new operation.
8. **Monotonic provider binding:** generation, incarnation, term, revision, and
   sequence are exact commitments. A lower retained high-water value or a
   conflicting branch is never accepted.
9. **Signer containment requirement:** two different decisions or signatures
   for one operation must fail closed when both are visible. S11 has no global
   witness or production quarantine mechanism and cannot prove signer
   non-equivocation.
10. **No lease/currentness-at-use claim:** the journal-owned authority
    commitment check and replay
    consume share L1, but a later signature or local action is not thereby
    current at use time. A later revocation cannot recall a historical
    observation.

The shared journal can reject a conflicting value that reaches the same local
CAS. The suite does not construct independent split-brain journals or a signer
rollback, and cannot prove that all branches were observed. Global signer
non-equivocation requires an external witness, transparency mechanism, or
equivalent owner-approved evidence that S11 does not provide.

## Threat scenarios and injected cut points

The contract enumerates thirteen threat scenarios so later adapters cannot
silently drop them. They are not thirteen implemented crash injectors. The
current Rust model has exactly six injected failure cuts: L1 before commit, L1
commit acknowledgement loss, signer execution followed by timeout, verified
signature loss before L2, L2 before commit, and L2 commit acknowledgement
loss. Other rows below are exercised by initial state, exact lookup/duplicate
delivery, signer-field faults, retained-witness journal mutation, or concurrent
workers, or remain explicit unproved successor requirements.

| Cut | Durable state after recovery | Allowed action |
| --- | --- | --- |
| before L1 begins | `ABSENT` | no original-operation retry; a policy-approved later attempt requires a new operation ID and challenge |
| during L1 before commit | `ABSENT` | transaction aborts completely; no partial reservation or consume |
| L1 committed, commit acknowledgement lost | `DECISION_COMMITTED_UNSIGNED` | authoritative lookup, then exact signing resume only |
| after L1, before signer request | `DECISION_COMMITTED_UNSIGNED` | exact signing resume only |
| signer request sent before execution | `DECISION_COMMITTED_UNSIGNED` | enumerated requirement; exact signing resume only after timeout/ambiguity |
| signer executed, response lost or timed out | `DECISION_COMMITTED_UNSIGNED` | exact re-sign of the same bytes/key version; exactly-once remains unproved |
| signer response received before synthetic field/signature verification | `DECISION_COMMITTED_UNSIGNED` | signer-fault shape; discard unverified response |
| signature verified before L2 | `DECISION_COMMITTED_UNSIGNED` | exact L2 CAS, or exact re-sign after process loss |
| key disabled, rotated, or destroyed before L2 | `DECISION_COMMITTED_UNSIGNED` | external-adapter requirement; no key substitution |
| during L2 before commit | `DECISION_COMMITTED_UNSIGNED` | exact state lookup, then exact resume/CAS |
| L2 committed, commit acknowledgement lost | `SIGNED_COMMITTED` | return the stored exact receipt; do not re-sign |
| L2 committed, caller response lost or duplicated | `SIGNED_COMMITTED` | byte-identical read-only delivery |
| database/provider snapshot rollback or branch merge | unknown/conflicting | retained L1 witness detects local disappearance only; signer rollback/split branch remain unproved |

For the injected L1 precommit cut, the operation, challenge, and replay indexes
are all absent. After modeled L1 commit, all three remain retained. The
injected pre-L2 cuts return no observation; after modeled L2 commit, lookup
returns only the stored private non-admission synthetic record.

## Rollback, split brain, and currentness race

A retained synthetic high-water observer can reject a lower generation, term,
revision, or sequence. Losing that observer makes a restored old database
indistinguishable from a legitimate earlier state. A same-generation restore
can also replay internally consistent signed data. S11 therefore does not
claim rollback detection or external durability.

Two leaders can each produce internally valid signed branches if their
database or signing authority is not genuinely fenced. A future adapter must
fail closed when both branches are presented, but S11 neither constructs that
split history nor supplies a quarantine service. Without an external common
witness, absence of a detected conflict is not proof of split-brain safety or
signer non-equivocation.

The synthetic lock removes the separation between checking its journal-owned
commitments/revoked flag and consuming the replay identity only inside this
sequence model: modeled revocation before L1 rejects, while L1 first records
one historical commitment and consumes the replay identity once in that
process. This is not independent S9 currentness verification. It does not make
a delayed signature, delayed delivery, or downstream side effect current at
use time. Instant revocation would require the real side effect to participate
in an equivalent external coordination protocol, which is outside S11.

## Reference provider research

No external resource is created by S11. For a later managed experiment,
Google Cloud Spanner is the reference database and an exact-version Google
Cloud KMS/Cloud HSM Ed25519 key is the reference signer.

- Spanner read-write transactions provide atomic database updates and external
  consistency, but transaction callbacks can be rerun and must not contain an
  external signing side effect
  ([transactions](https://docs.cloud.google.com/spanner/docs/transactions),
  [external consistency](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency)).
- A Spanner commit timestamp is assigned at database commit and is not a
  preexisting globally unique signer operation ID
  ([commit timestamps](https://docs.cloud.google.com/spanner/docs/commit-timestamp)).
- Cloud KMS supports `EC_SIGN_ED25519`; `asymmetricSign` addresses an exact
  CryptoKeyVersion and exposes request/response integrity fields, but it does
  not join a Spanner transaction or expose a queryable exactly-once signing
  operation
  ([algorithms](https://docs.cloud.google.com/kms/docs/algorithms),
  [asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign),
  [data integrity](https://docs.cloud.google.com/kms/docs/data-integrity-guidelines)).

For self-hosted fault injection, etcd transactions are a useful reference CAS
store and OpenBao Transit Ed25519 is a useful exact-version signer. They remain
separate atomic and rollback domains.

- etcd transactions provide atomic compare-and-update behavior, while snapshot
  restoration can move revisions backward and revision bumping is an operator
  recovery mechanism rather than a cryptographic anti-rollback anchor
  ([API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/),
  [recovery](https://etcd.io/docs/v3.6/op-guide/recovery/)).
- OpenBao Transit supports Ed25519 and explicit key versions, but its signing
  response is not an atomic database commit or an exactly-once operation
  receipt
  ([Transit API](https://openbao.org/api-docs/secret/transit/)).

These references justify the outbox shape, not production admission. Neither
stack supplies a database/KMS common transaction, an owner pin, complete
split-brain fencing, rollback-independent witnessing, instantaneous
revocation, or physical key-deletion proof.

## Tests and falsifiers

The S11 suite covers deterministic framing/signing, L1 all-or-none indexes at
its injected precommit cut, L2 all-or-none local storage at its injected
precommit cut, permanent consume while signing remains pending, typed L1
witness recovery, signer timeout and signature loss, acknowledgement and
response-delivery loss, stable duplicate delivery, selected
operation/request/challenge/replay conflicts, every synthetic journal-owned L1
commitment substitution, signer key/message/signature binding, wrong public-key
fast paths, monotonic floors, impossible phase/index combinations, explicit L2
checksum malleability, local retained-witness rollback ambiguity, concurrent
create-only L1 and exact L2 workers over one shared journal, revocation
ordering, and the no-network/no-public-constructor/no-Bridge/no-`StateStore`
boundary.

It does not prove or fully simulate an independent split-brain branch, signer
rollback, global signer equivocation detection, process crash, external
database durability, or all thirteen enumerated scenarios. Those remain
falsifiers and successor requirements, not positive evidence.

The experiment is falsified if an aborted L1 leaves a reservation, a committed
L1 releases an identity, recovery recomputes a decision, timeout switches key
versions, `DECISION_COMMITTED_UNSIGNED` produces an observation, modeled L2
stores an unverified or mismatched signature, duplicate delivery mutates state,
an ambiguity falls back locally, the public L2 checksum is described as an
authenticated persistence receipt, or any synthetic result is described as
external production evidence.

## Evidence and admission boundary

S11 may claim only
`SYNTHETIC_TWO_LEVEL_OUTBOX_SEQUENCE_AND_FAULT_MODEL_EVIDENCE`. It cannot prove:

- database/KMS cross-service atomicity;
- exactly-once signer execution;
- process-crash or external database durability;
- rollback protection or split-brain fencing;
- signer or provider non-equivocation;
- production KMS/HSM custody, rotation, revocation, or destruction;
- owner-pinned trust; or
- currentness at the time a downstream side effect executes.

The successor remains `NOT_ADMITTED`. Every S10 admission and external receipt
remains null. New S11 receipts for atomic authority operation, atomic replay
consume, database/KMS atomicity, exact-version signing, signature persistence,
signer non-equivocation, and currentness at use also remain null. The synthetic
model does not close
`RECOVERY_OPERATION_SUBMISSION_ATOMICITY_UNIMPLEMENTED`; it refines that gap
into an executable model while production implementation and attestation
remain absent.

No side effect is unlocked.

## Next admissible step

Do not attach S11 to Bridge. A later tranche may add a pure verifier for exact
stored S9 decision bytes without calling `request_currentness` again, still
returning only private non-admission evidence. A production adapter remains
gated on owner-selected database and custodian infrastructure, independently
delivered trust anchors, real fault/recovery evidence, and admitted
linearizability, durability, fencing, rollback, signer, custody, revocation,
and currentness-at-use receipts. Until then the only correct decision is
`BLOCKED_FAIL_CLOSED`.
