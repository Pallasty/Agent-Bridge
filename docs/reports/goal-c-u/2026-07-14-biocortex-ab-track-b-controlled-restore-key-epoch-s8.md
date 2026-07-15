# BioCortex / Agent-Bridge Track B Controlled-Restore Key Epoch S8

Date: 2026-07-14

Baseline: `7819e61f5468bb84061e6cbe111c327f63dc63bf`

Decision: `BLOCKED_FAIL_CLOSED`

Status: `SYNTHETIC_CONTROLLED_RESTORE_KEY_EPOCH_ADMISSION_IMPLEMENTED_ONLINE_AUTHORITY_SIMULATED_SAME_EPOCH_ROLLBACK_UNRESOLVED_NOT_AUTHORIZED_NOT_TRANSPORT`

## Result

S8 implements the previously preregistered restore-bound key-epoch rule as a
private, default-off, executable admission protocol. It binds one active epoch
to three separate key roles, an S7 registry generation, exact S6 payload bytes,
receiver/build/allowlist commitments, and online challenge-bound currentness.
The synthetic state machine fences the old epoch before the exact next epoch
can become active and never falls back to the local S7 sidecar when currentness
is absent or indeterminate.

The implementation remains deliberately unreachable from normal runtime code:

- the feature is not default;
- the module is private and has no crate re-export;
- the authority and capability constructors are `cfg(test)` only;
- StateStore and the main state database are unchanged;
- Bridge does not forward S6, S7, or S8; and
- no receiver, network I/O, cross-repository transport, or BioCortex runtime
  influence is added.

## Security interpretation

This result is controlled-restore fencing, not complete anti-rollback. Old
epoch rejection is conditional on an external currentness authority that does
not roll back with the sidecar, unique challenges, receiver quiescence, and
irrecoverable destruction of old keys. None of those production conditions has
a repository attestation or owner-approved KMS/HSM integration.

Three passing paths are intentionally negative evidence:

1. restoring a pre-consume S7 snapshot within the same active epoch erases the
   tombstone and permits the packet again; and
2. revocation after the online currentness response can race the subsequent
   local S7 consume and allow one lease-bounded admission; and
3. replaying a cached response with the same reused challenge can make stale
   currentness look valid to a nonconforming provider.

The synthetic authority keeps its reuse burn sets only inside one in-memory
instance. Reconstructing that authority loses the burn history. A database and
authority restored together, same-identity clone/fork, challenge replay by a
bad external provider, and privileged recovery of old keys also remain
unresolved.

Closing same-epoch rollback or instant revocation would require an external
linearizable authority to consume the concrete replay identity in its own
atomic operation. S8 makes no dual-store atomicity or exactly-once claim.

## Implementation evidence

The Rust contract includes:

- an exact epoch-record digest chained to its predecessor;
- strict `+1` epoch sequencing with checked overflow;
- distinct, nonzero handle, inner, outer, and synthetic authority keys;
- in-instance permanent non-reuse of role IDs/fingerprints, generation,
  restore-event, and revocation-checkpoint commitments;
- an outer domain-separated HMAC over all epoch bindings plus the exact S6
  payload bytes;
- the existing S6 exact-byte HMAC and S7 durable tombstone consume;
- an S6-compatible payload size cap before outer hashing;
- online challenge-bound currentness with no cached-receipt shortcut;
- no active response from closed, pending, or revoked state; and
- immediate release of the temporary outer-authentication buffer before the
  single S6 payload parse, limiting peak memory.

The independent Python checker reconstructs the record digest, outer HMAC, and
currentness HMAC. The frozen known answers are:

```text
policy_sha256              82dd7ee0cd71897d8cc274db05fb8ae4f88bfe8dfcd7f17b5622b731a72cde7c
epoch_record_sha256        19c19488aa3826bbea780bdf93c04f711b0c154a9a493f2d0359ddec9fab236f
outer_hmac_sha256          cfc4aa32f0b131c75d9e0b0565f256eb3ceca239e22bbbc6577e56f1acfa47ab
currentness_hmac_sha256    a8668b2c6e7f55aa46c551c7c9d1ee0190b4074b4765bc69781b2a10d3adbb11
```

## Verification

Low-memory targeted verification completed with
`CARGO_BUILD_JOBS=1`, `CARGO_INCREMENTAL=0`, `RUSTFLAGS=-C debuginfo=0`,
one Cargo job, disabled default ONNX features, offline locked dependencies, and
one test thread.

- S8: 14 passed, 0 failed;
- deterministic S8 checker: two byte-identical passes;
- historical S7 checker: unchanged receipt;
- historical S6 checker: unchanged receipt;
- Track B context-sampling checker: unchanged receipt; and
- focused Rust formatting and `git diff --check`: passed.

The committed gate repeats S8 plus the historical S7, S6, S5, S4, and S2 Rust
regressions and default-off Store/Bridge checks under the same low-memory
profile. It verifies a single-parent feature commit, a closed path allowlist,
regular-file modes, a symlink-free archive, deterministic receipts, report
digest bindings, and an unchanged clean HEAD.

## Independent review

Three read-only reviews covered code, security, and artifacts. The final code
and security review found no P0 or P1 logic issue. Findings resolved before the
artifact freeze included:

- cap the payload before constructing the outer HMAC message;
- prove the revocation/currentness race as negative evidence;
- reject all-zero role keys and separate the fourth authority key;
- exercise actual outer/currentness HMAC tag failures;
- remove the duplicate near-4 MiB payload parse and release the outer buffer;
- fence closed on theoretical authority-sequence overflow;
- scope burn-history claims to one synthetic authority instance; and
- distinguish authority-state single-active semantics from in-flight local
  admissions.

The artifact review's remaining procedural findings—the report itself and the
gate executable mode—are closed by this report and the committed `100755` mode.

## Admission status

The successor candidate remains `NOT_ADMITTED`. All admission receipt fields
remain null. The original blockers are unchanged:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

S8 additionally retains:

```text
CURRENTNESS_CHALLENGE_UNIQUENESS_UNATTESTED
EXPECTED_EPOCH_CURRENTNESS_EXTERNAL_CUSTODY_UNATTESTED
INSTANT_REVOCATION_UNAVAILABLE_WITH_LOCAL_CONSUME
OLD_EPOCH_KEY_DESTRUCTION_UNATTESTED
SAME_EPOCH_RESTORE_DETECTION_UNAVAILABLE
```

No side effect is unlocked.

## Artifact manifest

- `crates/store/Cargo.toml`: `bb697095ce1c0b2322eac47ab8b1988f4a404b8f574e1b831db23e77cdaa56e1`
- `crates/store/src/temporal_replay_transport.rs`: `4bb9f28d802bc0eb3772f47eab9e487087389b2f5a675dadb8939722f43dae2c`
- `crates/store/src/temporal_replay_transport/durable_replay_registry.rs`: `10f3d1041e594f46b00ebf3db9800c6eb5adc44330978d11e4814ec5cf0c711d`
- `crates/store/src/temporal_replay_transport/restore_bound_key_epoch.rs`: `a252459ec21df5f2c4ecb251e61433017d5a2a44e9f14b1b886452da485f43b4`
- `docs/design/MEMORY_TEMPORAL_CONTROLLED_RESTORE_KEY_EPOCH_S8_2026_07_14.md`: `cd04d7e2b2abd71ca69b18f990411178a42a1b455ea89417e89829c31bc3eac1`
- `docs/design/fixtures/biocortex-ab-track-b-controlled-restore-key-epoch-s8-v0.json`: `039ec8237afa9b2ea3340918a2924f78f89223abbd4034d41c6d82a2e1519573`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s8-v0.json`: `c01e686d104392269d57c39a9a240b203016639c65f379f992e74d30248c5817`
- `scripts/check-memory-temporal-controlled-restore-key-epoch-s8.sh`: `7775421675e7631e4847a3f92035828568d7d06fe8a1d45cdde3f1df4e36045b`
- `scripts/eval/check_memory_temporal_controlled_restore_key_epoch_s8.py`: `32dd93431ce131b193bef02f7e4fef4795e24daf982eb690b3cd679570c495d8`
- `scripts/eval/fixtures/memory_temporal_controlled_restore_key_epoch_s8.expected.v0.tsv`: `0ee478abbfc241d77138bdaac48fab92fd8caf0eec48c7f6acf6655b58d530e5`

## Next admissible step

Do not connect S8 to Bridge. The next tranche should either select an
owner-approved external currentness/custody interface and preregister its
freshness, lease, challenge, revocation, recovery, and failure semantics, or
stop at this synthetic boundary. A file stored beside the sidecar, a local
SQLite epoch table, or a self-contained signed receipt is not an external
anti-rollback anchor.
