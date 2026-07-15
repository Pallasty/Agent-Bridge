# BioCortex / Agent-Bridge Track B Atomic Authority Operation S11

Date: 2026-07-14

Status:
`ATOMIC_AUTHORITY_OPERATION_OUTBOX_PREREGISTERED_SYNTHETIC_DB_ONLY_DB_KMS_NON_ATOMIC_EXACTLY_ONCE_UNPROVED_NO_PROVIDER_NO_CUSTODIAN_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S11 preregisters the two-level authority-operation outbox that S10 recovery
requires. Under one shared synthetic-journal lock, L1 verifies caller-supplied
commitments against journal-owned generation, provider identity, authority
snapshot, canonical-decision, trust-policy, and signer commitments; atomically
reserves the operation and challenge; consumes the concrete replay identity;
freezes an exact framed L1 signing message; and persists
`DECISION_COMMITTED_UNSIGNED`. It does not derive or independently reverify raw
S9 decision bytes.

After a synthetic signer response is locally authenticated, modeled L2
compare-and-swaps that exact record to `SIGNED_COMMITTED` while storing the
signature, a synthetic revision, and a public row checksum.

Those are the only two persisted states. A signer response observed between
them is volatile, not a third state. Exact recovery may re-sign only the same
message with the same key version; it may never repeat L1, recompute the
decision, substitute a key, release a consumed identity, or call S9
`request_currentness` again.

No database, provider account, KMS/HSM/OpenBao endpoint, credential, owner
trust pin, production adapter, public constructor, Bridge feature,
`StateStore` surface, BioCortex runtime effect, or transport was added.

## State and failure semantics

The legal path is:

```text
ABSENT -> DECISION_COMMITTED_UNSIGNED -> SIGNED_COMMITTED
```

L1 is all-or-none across operation, challenge, replay identity, journal-owned
commitments, provider monotonic metadata, sign-job identity, and signer
version. Modeled L2 is all-or-none across the verified signature, public local
checksum, and final state.
`DECISION_COMMITTED_UNSIGNED` cannot produce a recovery observation;
`SIGNED_COMMITTED` maps to typed lookup result `COMMITTED`, which remains
private non-admission sequence evidence.

Lookup distinguishes `NOT_FOUND`, `PENDING(L1_WITNESS)`, and
`COMMITTED(SYNTHETIC_RECORD)`. Conflict and indeterminacy are fail-closed
errors. `begin_exact_once` is create-only: after an ambiguous L1 acknowledgement
the caller must look up the exact operation and use the returned typed L1
witness with `resume_exact_from_l1`. Witness disappearance or substitution
fails closed and never recreates L1.

An exact duplicate sees the stored state. At `DECISION_COMMITTED_UNSIGNED` it
can resume only the exact signing job; at `SIGNED_COMMITTED` it returns the
exact stored synthetic record without mutation. A different request,
challenge, replay identity, decision, signer, generation, term, revision,
sequence, signature, or checksum fails closed when visible to the shared
journal. The model has no external branch witness or quarantine service.

Ed25519 authenticates only the exact frozen L1 decision message. The synthetic
L2 revision and checksum are outside that signature and are publicly
recomputable; they do not authenticate journal persistence or prove a database
commit. The verified observation excludes them. `SIGNED_COMMITTED` is only a
state observed in the shared in-process journal, not an external receipt.

Signer timeout is intentionally a liveness failure, not permission to undo
the transaction. Once L1 commits, the challenge and replay identity stay
consumed even if no signature can ever be obtained. A timeout after the signer
executed may lead to an exact re-sign, so S11 cannot claim that signing happened
exactly once.

## Fault model

The experiment enumerates thirteen threat scenarios spanning pre-L1, intra-L1,
lost L1 acknowledgement, pre-sign, ambiguous or lost signer response,
pre-verification, post-verification, key-state change, intra-L2, lost L2
acknowledgement, lost or duplicate caller delivery, and database/signer
rollback or branch merge. This is a completeness checklist, not thirteen
implemented crash injectors.

The Rust sequence model has six injected failure cuts: L1 before commit, L1
acknowledgement loss, signer execution followed by timeout, verified-signature
loss before L2, L2 before commit, and L2 acknowledgement loss. Other scenarios
are covered only by initial state, typed lookup, selected signer-field faults,
retained-witness mutation, or concurrent workers over the same journal, or
remain unimplemented successor requirements.

At the injected L1 precommit cut every modeled index is absent. After modeled
L1 commit all identities remain reserved and only typed-witness exact sign
recovery is allowed. The injected pre-L2 cuts return no observation. After
modeled L2 commit recovery returns the stored synthetic record and does not
call the signer again.

The executable matrix covers selected operation/request/challenge/replay
conflicts, every journal-owned L1 commitment substitution, signature and
response-delivery loss, synthetic signer key/message/signature mismatches,
wrong public-key fast paths, monotonic floors, impossible phase/index
combinations, explicit public-L2-checksum malleability, retained-witness
rollback ambiguity, concurrent L1/L2 workers over one shared journal, and
revocation-before-versus-after-L1 interleavings. It does not prove independent
split-brain behavior, signer rollback, global signer non-equivocation, or
external quarantine.

## Evidence boundary

The only positive claim is
`SYNTHETIC_TWO_LEVEL_OUTBOX_SEQUENCE_AND_FAULT_MODEL_EVIDENCE`. The shared
in-process model cannot prove:

- database/KMS cross-service atomicity;
- exactly-once KMS or Transit signing;
- external database durability or linearizability;
- rollback protection or split-brain fencing;
- signer non-equivocation or production key custody;
- an owner-pinned trust anchor; or
- currentness when a later downstream side effect executes.

Spanner plus exact-version Cloud KMS/Cloud HSM remains the managed research
reference; etcd plus OpenBao Transit remains the self-hosted fault-injection
reference. Both are database/signer sagas with separate commit and rollback
domains, not a common atomic transaction.

## Verification

The final gate requires deterministic S11 checker output on two passes, exact
fixture/schema and independent known-vector validation, S11 Rust tests,
archived S10 verification plus retained S10 semantic checks, historical S9
through S2 regressions, Store feature/default-off builds, Bridge historical-
feature/default-off builds, low-memory one-job execution, formatting, JSON,
shell syntax, clean-tree, topology, exact-path, mode, archive, and report digest
checks.

Final validation result: `PASS` (deterministic checker/fixture, 29 S11 tests,
S10-S2 regressions, Store and Bridge feature/default-off builds, formatting,
schema, shell, path, topology, archive, mode, and digest checks).

Expected S11 Rust test count: `29`.

## Review

Independent code, security, and artifact review result:
`PASS_P0_0_P1_0_P2_0`.

## Admission status

The successor remains `NOT_ADMITTED`. Every inherited admission, authority,
provider, custody, recovery, durability, rollback, fencing, and revocation
receipt remains null. New S11 receipts for atomic authority operation, atomic
replay consume, database/KMS atomicity, exact-version signing, signature
persistence, signer non-equivocation, and currentness at downstream use are
also null.

The model leaves the existing S10 gaps open and adds:

```text
ATOMIC_AUTHORITY_OPERATION_EXTERNAL_DATABASE_UNIMPLEMENTED
DATABASE_KMS_CROSS_SERVICE_ATOMICITY_UNATTESTED
KMS_EXACTLY_ONCE_SIGNING_UNPROVED
EXACT_VERSION_SIGNING_CUSTODY_UNATTESTED
OPERATION_OUTBOX_EXTERNAL_DURABILITY_UNATTESTED
SIGNATURE_PERSISTENCE_EXTERNAL_DURABILITY_UNATTESTED
SIGNER_NON_EQUIVOCATION_UNATTESTED
CURRENTNESS_AT_DOWNSTREAM_USE_UNATTESTED
```

The decision remains `BLOCKED_FAIL_CLOSED`; no side effect is unlocked.

## Artifact manifest

- `crates/store/Cargo.toml`: `bff674220aafad7d9db2f91c71f59348f7a3b316eb0ac5f78adf4d811f8f79ee`
- `crates/store/src/temporal_replay_transport.rs`: `1880e0f1a95dd962cc611f19139da5b74e4c5a991fe89d482ad032677827ed8a`
- `crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs`: `ffe01c13aadec867921ffd23f39f3ecc5d443bc44d30654f7fcd0be10e04793c`
- `docs/design/MEMORY_TEMPORAL_ATOMIC_AUTHORITY_OPERATION_S11_2026_07_14.md`: `6b352ed02a3dcbac135f59ba94c79d32e80354dfb68f3c4a7193011cc1c909af`
- `docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json`: `eaca1280836bb31a3e1d0ce11173c6e34dbddf24a19e270af21d579428327db2`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json`: `2d932c2b82fa41478ad42630bc9bae60467088027d046e7c14bed6a776d69cac`
- `scripts/check-memory-temporal-atomic-authority-operation-s11.sh`: `5a72d05ef7eaf3687c53cc2ac8e1cd1908e87b2d8fcc31b87567afb2beabb11a`
- `scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py`: `bb92bad4648d865a3cf72b6c00c4f6bfaad07b6f3a3e0ece48e938c85c1b45a7`
- `scripts/eval/fixtures/memory_temporal_atomic_authority_operation_s11.expected.v0.tsv`: `f60e553cb8da0f76f0d6de61c22f7018538825e7b6d47ef8cb471e84f632f903`

## Next admissible step

Do not connect S11 to Bridge. A later tranche may add a pure verifier for the
exact stored S9 decision without making a second currentness request, while
keeping the result private and non-admitting. Production remains gated on
owner-selected external infrastructure and real durability, linearizability,
fencing, rollback, signer, custody, revocation, and currentness-at-use
evidence.
