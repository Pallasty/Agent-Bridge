# BioCortex AB Track B durable replay S7

Date: 2026-07-14

Status:
`SYNTHETIC_LOCAL_DURABLE_REPLAY_TOMBSTONE_IMPLEMENTED_SUCCESSOR_GATE_PREREGISTERED_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Result

S7 adds a private, default-off, content-minimized local SQLite replay sidecar
and an explicitly closed successor-payload admission gate. The sidecar is
separately provisioned, path/generation/schema pinned, insert-only, and opened
without create or symlink following. It persists the existing S6 replay
identity across restart, independent connections, actual process contention,
and the tested crash boundaries.

S7 also hardens the S6 verifier: a replay receipt must return the same replay
key and scope commitments that the verifier asked to consume. The private S7
wrapper additionally requires a durable receipt. A substituted or ambiguous
receipt releases no verified token.

S7 does not deploy or enable a transport. It adds no StateStore method, main
`state.db` migration, Bridge feature, MCP/CLI/daemon endpoint, network or
filesystem receiver, BioCortex consumer, default path, or non-test constructor.
The successor gate remains `NOT_ADMITTED`, all authority/custody/attestation
receipts remain absent, and S5's authenticated false/NONE boundary is unchanged.

## Storage contract

The dedicated sidecar freezes:

```text
application_id                 1094865463 (ABR7)
user_version                   1
journal_mode                   DELETE
synchronous                    EXTRA (3)
busy_timeout                   1500 ms
schema_manifest_sha256         686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466
per-tombstone commitments      3 x BLOB(32) = 96 bytes
```

The only per-request values are replay-key, scope, and payload SHA-256
commitments. No raw nonce, key ID, trial, case, request, route, payload, handle,
evidence ID, value, consumption time, or expiry is stored. `STRICT`,
`WITHOUT ROWID`, exact SQL-schema hashing, fixed-length checks, and immutable
metadata/update/delete triggers close the schema. Expiry never deletes or
releases a nonce.

Normal open is `READ_WRITE + NO_CREATE + NOFOLLOW`. A missing file remains
missing and fails closed. A separately supplied 32-byte generation ID plus the
canonical path, application/user identity, schema digest, PRAGMAs, permissions,
temporary schema, and `quick_check` are verified. This detects missing,
foreign, wrong-generation, structurally drifted, or overly permissive files; it
does not detect restoration of an old valid copy with the same generation. The
checks are not tamper resistance against the same UID/database writer: a writer
can temporarily drop a trigger, delete a tombstone, and recreate the exact
trigger before the next open, leaving the pinned schema digest unchanged.

## Atomicity and crash result

Consumption uses `BEGIN IMMEDIATE` followed by one targeted
`INSERT ... ON CONFLICT(replay_key_sha256) DO NOTHING`.

- one inserted row plus confirmed commit is the only durable success;
- the same immutable scope/payload is terminal `REPLAY`;
- another scope/payload under the same key is terminal `SCOPE_COLLISION`;
- busy, locked, schema, integrity, I/O, or commit uncertainty is
  `INDETERMINATE` and produces no token;
- there is no check-then-insert, broad ignore, replace/update, cleanup, expiry
  GC, or in-memory fallback.

An injected result loss after a confirmed commit returns indeterminate, then a
fresh open rejects the retry as replay. An actual child killed after insert but
before commit leaves no tombstone and a later first consume succeeds. An actual
child killed after commit leaves the nonce burned and a later consume rejects.

## Successor gate

The gate freezes requirements without fabricating evidence. A future successor
must use a new schema/version, candidate ID, exact payload profile, schema
digest, and authentication domain, and must bind external authority/custody,
build/producer, receiver/allowlist, capture/provenance, deletion, revocation,
purpose, lifetime, and side-effect evidence. Repository-owner permission for
reversible research, a durable local tombstone, an outer route, or a sibling
review artifact cannot raise the protected S5 v0 boundary.

Cross-version nonce reuse and key-ID reassignment remain forbidden. The S6
known replay identity remains:

```text
7c21a79214624b4c1c259d38aeff4b228d4df0071d180be249b78a5c47e1e8a5
```

## Verification

Low-memory validation used one Cargo build job, disabled incremental
compilation, stripped debug information, disabled default ONNX features,
offline locked dependencies, and one test thread.

Results:

- S7 durable replay: 13 passed, 0 failed, plus 3 ignored child-process helpers
  invoked by parent tests;
- S6 detached verifier regressions: 7 passed, 0 failed;
- S5 candidate-binding regressions: 7 passed, 0 failed;
- S4 projection regressions: 7 passed, 0 failed;
- S2 temporal-ledger regressions: 14 passed, 0 failed;
- S7 store feature check: passed;
- store default-off check: passed;
- Bridge with only its existing S5 feature: passed;
- Bridge default-off check: passed;
- S7 checker: exact deterministic receipt, 30 independent mutation
  rejections;
- historical S6 checker: unchanged and passed;
- `git diff --check`: passed.

Existing warnings about a Greek mixed-script test identifier, an unused vector
helper, and pre-existing Bridge private/dead items remain. S7 introduced no new
build warning.

The tests establish a synthetic local same-file at-most-once contract, not
end-to-end exactly-once behavior. They make no latency, throughput, memory,
model-quality, BioCortex, neuroscience, or fermionic-algorithm performance
claim.

## Explicit limitations

S7 does not solve old-backup restore, valid same-generation file substitution,
hardlinks/multiple paths, database cloning/forking, multiple hosts, unreliable
network-filesystem locks, same-UID transient DDL/data tampering, or universal
hardware power-loss behavior. A runtime receiver would need an external
monotonic/anti-rollback anchor or a restore-bound key epoch plus a dedicated
service identity and protected parent directory before admission.

S7 has no async receiver, so async-worker cancellation behavior is not claimed.
Stable digest commitments are pseudonymous fingerprints, not anonymization.
Permanent nonce retention and physical privacy deletion remain an unresolved
policy tension.

The original five blockers remain unchanged:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

## Artifact digests

- `crates/store/Cargo.toml`: `86e40401fdb6c1d97e48d919d68d3a089cb04aba3ee85bcaeaede5b452351bcd`
- `crates/store/src/temporal_replay_transport.rs`: `c36769b4a26a3f3fe16b6e15903b957eff2bfd9edcd4fd4e707b83dd0ec6e8f9`
- `crates/store/src/temporal_replay_transport/durable_replay_registry.rs`: `e8a4b45f42086b97f48fc2970fa2b25b9302200f629e8ca7a4470f3fc1aac87b`
- `docs/design/MEMORY_TEMPORAL_DURABLE_REPLAY_S7_2026_07_14.md`: `9744bebb4bffec6c0816f5d6c264a71395354b964839e0401d0246cf4035ad53`
- `docs/design/fixtures/biocortex-ab-track-b-durable-replay-contract-s7-v0.json`: `8e4f895089f3085725988b50001ab77ec909b86b1dd203e304cc6b4a143a4c8c`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s7-v0.json`: `dec28c4a79e7573f0a296af43e5c03a68f61b8c13ddaef4384e19aa441500546`
- `scripts/check-memory-temporal-durable-replay-s7.sh`: `b8716a61cd4956041adf8d4b99c9fe37b8e23f3e2b524ffcd09256f1e6726e55`
- `scripts/eval/check_memory_temporal_durable_replay_s7.py`: `2143f08ceaccdb0fe1410977be8f6b5dd54499acb3c1e9824ecf4a3b024c37e0`
- `scripts/eval/fixtures/memory_temporal_durable_replay_s7.expected.v0.tsv`: `be12759410a2ad363e790624117572f7b5ec0620917c91341b8c2b4c98356204`

## Next step

After independent review and a committed clean-HEAD S7 gate pass, this tranche
may be merged and pushed. The next tranche should first establish an external
authority/custody decision for a genuinely new successor payload and choose an
anti-rollback/restore-bound key-epoch policy. A separate default-off async
receiver with cancellation/crash tests can be considered only after those
gates; attaching this code to Bridge now is not admissible.
