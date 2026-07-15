# Memory Temporal Controlled-Restore Key Epoch S8

Date: 2026-07-14

Decision: `BLOCKED_FAIL_CLOSED`

Status: `SYNTHETIC_CONTROLLED_RESTORE_KEY_EPOCH_ADMISSION_IMPLEMENTED_ONLINE_AUTHORITY_SIMULATED_SAME_EPOCH_ROLLBACK_UNRESOLVED_NOT_AUTHORIZED_NOT_TRANSPORT`

## Outcome

S8 makes the S7 “restore must change key epoch” rule executable behind the
default-off feature
`temporal-evidence-s8-restore-bound-key-epoch-synthetic`. It adds a private
admission wrapper and a test-only online authority state machine. No non-test
constructor exists, the module is not exported from `ab-store`, and Bridge does
not forward the feature.

This is controlled-restore fencing, not a complete anti-rollback mechanism.
The implemented result is conditional on two facts that the repository cannot
currently attest:

1. current epoch state is held by an online authority outside the S7 sidecar,
   host, and backup domain; and
2. every key from a fenced epoch is permanently unavailable after rotation.

The repository has no production KMS, HSM, keyring, revocation service,
currentness service, or custody receipt. S8 therefore simulates the online
authority with test-only HMAC material and keeps the production boundary
closed.

## Frozen predecessor

S8 is based on commit
`7819e61f5468bb84061e6cbe111c327f63dc63bf`. It preserves the S7 durable
contract at
`8e4f895089f3085725988b50001ab77ec909b86b1dd203e304cc6b4a143a4c8c`
and the S7 successor gate at
`dec28c4a79e7573f0a296af43e5c03a68f61b8c13ddaef4384e19aa441500546`.
The S7 SQLite schema is not migrated. S8 only adds a private generation
observation used to compare the already pinned S7 registry identity with the
active epoch record.

The Track B context-sampling determinism pack at
`06f54d4079e09d7728effd242d9dbf0e35f4d050e0d7a9f6a5fc9a8202b9445f`
is compatibility evidence only. It supplies no authority, custody, runtime, or
transport authorization.

## Closed key-epoch record

Every record commits to:

- an exact positive epoch and predecessor record digest;
- S7 contract and schema-manifest identities;
- a new S7 registry generation and restore-event commitment;
- receiver, build, allowlist, and revocation-checkpoint commitments;
- independent handle, inner transport, and outer channel key IDs and
  fingerprints; and
- the exact S8 policy digest.

All three key IDs and fingerprints must be distinct, and the fingerprint of an
all-zero 32-byte role key is forbidden. Within one synthetic authority instance,
key IDs, fingerprints, registry generations, restore events, and revocation
checkpoints are burned and cannot be reassigned. The in-memory test authority
does not preserve that history across authority reconstruction or restart.
Epochs advance by exactly one and fail closed on overflow.

The record is a commitment, not an attestation. A SHA-256 value cannot prove
that the described receiver, build, allowlist, restore, revocation state, or key
custodian exists.

## State machine

```text
CLOSED
  -> ACTIVE(E1)                         exact genesis only

ACTIVE(En)
  -> PENDING(E(n+1))                    fence En first, burn exact next identity
  -> REVOKED                            no active currentness

PENDING(E(n+1))
  -> ACTIVE(E(n+1))                     exact pending record only
```

The authority state has no dual-active grace period. An already in-flight local
admission can nevertheless outlive its currentness check, so receiver
quiescence and challenge uniqueness are separate operational preconditions.
`PENDING`, `REVOKED`, and `CLOSED` return no active currentness response.
Invalid transitions do not change state. A result lost after the transition to
`PENDING` leaves the old epoch fenced; the
only recovery demonstrated by S8 is to query the authority and activate the
exact precomputed pending identity. Local S7 fallback is forbidden.

A production workflow would additionally have to stop the receiver, advance
an external authority with atomic compare-and-swap, irreversibly revoke the old
keys, create and synchronize a new sidecar generation, and only then activate
the exact new record. S8 does not implement or claim those operational steps.

## Admission order

The private S8 wrapper performs the following checks before returning its
unforgeable local token:

1. enforce the S6 payload byte sentinel, then validate the closed epoch record
   and nonzero challenge;
2. authenticate the exact S6 payload bytes under the epoch-specific outer key
   and a new S8 domain;
3. bind the inner S6 permit key fingerprint and ID to the epoch;
4. bind the payload handle-key ID to the epoch;
5. bind the S7 registry generation to the epoch;
6. call the online authority and verify a challenge-bound active response;
7. run the complete S6 exact-byte verifier and S7 durable consume; and
8. return a private token only after the durable receipt identity matches.

An old packet cannot be made current by changing an epoch field: its outer
HMAC, inner HMAC, handle-key ID, and registry generation remain independently
bound. An authority timeout, unavailable result, stale response, authentication
failure, pending state, prior revocation, or result ambiguity returns no token.
The currentness check and local S7 consume are not one atomic operation: a
revocation that occurs between them can race one admission. S8 records that
behavior as negative evidence rather than claiming instant revocation.

The synthetic currentness response uses a fourth shared HMAC key, which must be
distinct from the handle, inner transport, and outer channel role keys, because
the code has no external signer. That is a deterministic test mechanism, not a
production signature or custody proof. Non-test code has neither an authority
implementation nor permit constructor.

## What the backup tests establish

The positive restore test advances from epoch 1 to epoch 2 and retains the
newer online authority state. Under those conditions:

- the epoch-1 packet is stale;
- an epoch-2 permit rejects the epoch-1 S7 generation; and
- S7 independently refuses to open the old database under the new generation.

The negative-evidence test intentionally restores a pre-consume S7 snapshot
without changing the active epoch or currentness state. The restored database
has the same generation, so the previously consumed packet is accepted again.
The passing assertion records this as `UNRESOLVED`; it is not a successful
anti-rollback test.

Consequently S8 does not detect:

- a sidecar rollback within one active epoch;
- a database and authority/currentness state rolled back together;
- reconstruction of the synthetic authority with an empty in-memory burn set;
- a clone or fork that retains the same epoch and generation;
- a privileged attacker that can recover old keys or forge currentness;
- instantaneous revocation between the online check and local consume; or
- an old challenge-bound response when a caller incorrectly reuses the same
  challenge and its external provider permits replay.

Closing same-epoch rollback requires a genuinely external linearizable replay
authority that atomically consumes the concrete replay identity. SQLite may be
a projection of such an authority, but a remote check plus a separate local
commit must not be described as atomic or exactly-once.

## Executable evidence

Fourteen non-ignored Rust tests cover:

- deterministic record, outer authentication, and currentness vectors;
- exact three-key binding and durable replay rejection;
- fence-before-activate ordering and no pending fallback;
- old database, old packet, and old-inner-key rejection;
- same-epoch snapshot rollback as explicit negative evidence;
- epoch decrement, repeat, skip, overflow, and identity reuse;
- cross-role collisions and historical fingerprint reuse;
- challenge substitution and authority unavailability;
- exact-byte and epoch-field tampering before replay consumption;
- explicit revocation;
- revocation after currentness as lease-bounded negative evidence;
- concurrent transition single-winner behavior; and
- pending transition result-loss recovery by exact external identity.

The deterministic checker independently reconstructs the record digest, outer
HMAC, and currentness HMAC. Historical S7, S6, S5, S4, and S2 regressions and
default-off Store/Bridge checks remain release gates.

## Unchanged admission boundary

The successor payload remains `NOT_ADMITTED`; S8 is an admission protocol for
the existing synthetic S6/S7 verifier path, not a successor schema or a
cross-repository packet. No BioCortex runtime influence, async receiver,
StateStore method, Bridge caller, side effect, or transport is added.

The original five blockers remain:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

S8 also records five operational gaps:

```text
CURRENTNESS_CHALLENGE_UNIQUENESS_UNATTESTED
EXPECTED_EPOCH_CURRENTNESS_EXTERNAL_CUSTODY_UNATTESTED
INSTANT_REVOCATION_UNAVAILABLE_WITH_LOCAL_CONSUME
OLD_EPOCH_KEY_DESTRUCTION_UNATTESTED
SAME_EPOCH_RESTORE_DETECTION_UNAVAILABLE
```

## Next admissible step

Do not attach this module to Bridge. The next tranche should select an actual
owner-approved external authority/custody interface and preregister its
freshness, revocation, challenge uniqueness, lease, and failure semantics. If
that external dependency cannot be supplied, the safe alternative is to stop
at S8 rather than convert a synthetic shared-key protocol into a runtime
authority.
