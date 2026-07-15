# Memory temporal durable replay S7

Date: 2026-07-14

Status:
`SYNTHETIC_LOCAL_DURABLE_REPLAY_TOMBSTONE_IMPLEMENTED_SUCCESSOR_GATE_PREREGISTERED_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S7 implements the next local safety substrate without activating a receiver:

1. a private, default-off SQLite replay-tombstone executable contract now
   survives restart, concurrent connections, real process contention, and the
   tested pre/post-commit crash boundaries;
2. an explicit successor-payload admission gate now records that no successor
   is admitted and enumerates the external authority, custody, producer, build,
   capture, deletion, allowlist, and revocation evidence that would be required;
3. the S6 verifier now rejects a registry receipt whose replay-key or scope
   commitment differs from the request, and the private S7 wrapper additionally
   requires a durable receipt.

This does not implement a transport. There is no Bridge feature forwarding,
StateStore method, MCP/CLI/daemon/filesystem receiver, BioCortex caller, default
database path, or non-test constructor. S5's authenticated payload still says
`cross_repository_transport_authorized=false`, `live_binding_satisfied=false`,
`biocortex_runtime_influence=false`, and `side_effects_unlocked=NONE`.

## Why the registry is a dedicated sidecar

The Agent-Bridge working database is a v43 source-of-truth store with a frozen
temporal-evidence schema identity. A feature-gated v44 would make a database
opened by the S7 build incompatible with a feature-off build; an unconditional
v44 would mutate ordinary deployments even though S7 is not authorized.
Moreover, a replay ledger belongs to a future receiver trust boundary, not the
source truth ledger.

S7 therefore leaves `state.db`, `SqliteStore`, and `StateStore` untouched. Its
private sidecar has:

```text
application_id: 1094865463 (ASCII ABR7)
user_version:   1
journal_mode:   DELETE
synchronous:    EXTRA (PRAGMA value 3)
busy_timeout:   1500 ms
schema digest:  686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466
```

The low-frequency security ledger uses rollback-journal `DELETE` plus
`synchronous=EXTRA`. This avoids a deployment or backup silently omitting a WAL
side file and asks SQLite for the stronger rollback-journal synchronization
profile. S7 tests crash behavior on the bundled SQLite build; it does not claim
universal hardware power-loss durability.

## Provisioning and identity

Provisioning and normal opening are separate operations:

- explicit test-only provisioning uses create-new semantics and refuses an
  existing path;
- normal open is read/write, no-create, no-follow;
- the path must be a regular non-symlink file and, on Unix, mode `0600` or
  stricter;
- the caller supplies a separately pinned 32-byte registry generation ID;
- application ID, user version, generation ID, complete `sqlite_schema` digest,
  column layout, temporary schema, connection PRAGMAs, and `quick_check` are
  verified before use and again before the conditional insert.

A missing database is an error and remains missing. It is never silently
recreated. This closes the simple "delete the ledger, then replay" failure mode.
It does not prevent a privileged actor from restoring an old byte-for-byte copy
with the same generation ID. Production use would still require an external
monotonic/anti-rollback anchor or a key-epoch policy bound to controlled backup
restoration.

The schema digest, triggers, and Unix file mode are drift detectors, not a
tamper-proof boundary against the same UID or another principal with database
write access. Such a principal can drop a trigger, delete a tombstone, and
recreate the byte-identical trigger before the next open; the final schema hash
and `quick_check` then pass. A runtime deployment would therefore also require
a dedicated service identity and protected parent directory in addition to the
external monotonic/restore-bound anchor.

## Content-minimized permanent tombstone

The metadata table contains only its singleton and the pinned generation ID.
Each replay tombstone contains exactly three fixed-length commitments:

```text
replay_key_sha256  BLOB(32) PRIMARY KEY
scope_sha256       BLOB(32) NOT NULL
payload_sha256     BLOB(32) NOT NULL
```

The tables are `STRICT` and `WITHOUT ROWID`. Triggers reject tombstone update
and deletion and make registry metadata immutable. There is no expiry,
consumption time, cleanup, update, or garbage-collection column/path. Expiry is
only an admission-validity check; it is never a retention deadline. A transport
key/nonce pair remains burned after payload expiry or key revocation.

No raw nonce, key ID, case, request, trial, route, payload, evidence ID, handle,
or value is stored. The 96 commitment bytes are still stable pseudonymous
fingerprints, not anonymous data and not proof of legal/privacy compliance.
Permanent replay safety and physical deletion therefore remain an explicit
unresolved policy tension.

## Atomic state machine

Every consume attempt opens and revalidates the same pinned sidecar, then runs:

```text
BEGIN IMMEDIATE
-> revalidate identity/schema
-> INSERT ... ON CONFLICT(replay_key_sha256) DO NOTHING
-> inserted=1: COMMIT; only confirmed commit may return durable success
-> inserted=0: read immutable winner in the same transaction
   -> same scope + payload: REPLAY
   -> any different commitment: SCOPE_COLLISION
```

There is no check-then-insert, `INSERT OR IGNORE`, `REPLACE`, update-on-conflict,
or memory fallback. Busy, locked, readonly, integrity, schema, I/O, connection,
or commit ambiguity produces no verified token. Exact replay is a terminal
rejection, not an idempotent success.

S6 previously trusted a sealed registry to return the same replay identity it
was asked to consume. S7 hardens that boundary: the verifier compares the
returned replay-key and scope commitments to its own fixed-size values. Any
substitution is indeterminate and releases no token. The S7-specific wrapper is
concrete over the private durable registry and also requires `durable=true`.

## Successor admission gate

S7 does not invent the missing authority evidence. The machine-readable gate is
`NOT_ADMITTED` and keeps every decision/custody/attestation receipt null.

Any future successor must have a new schema ID/version, candidate ID, exact
payload profile, schema digest, and authentication domain. It cannot mutate S5
v0 in place or reinterpret authenticated false boundary fields as true. Outer
route metadata, a durable receipt, repository-owner permission to conduct
reversible research, or sibling review artifacts cannot substitute for:

- a transport-scoped authority decision and custodian receipt;
- independent handle/inner/outer key custody, rotation, and revocation records;
- current build attestation and producer runtime identity;
- destination receiver identity plus an externally pinned allowlist;
- capture authorization/provenance and deletion-mechanism decisions; and
- an exact permitted purpose, trial scope, lifetime, and side-effect class.

Cross-version nonce reuse and key-ID reassignment remain forbidden. The S6
known replay vector remains pinned, but a future version/domain/key transition
requires its own review rather than an implicit compatibility assumption.

## Verification matrix

Thirteen non-ignored Rust tests cover:

- full exact-byte verification followed by a durable commit and restart replay;
- receipt identity substitution rejection;
- restart and post-expiry permanent replay rejection;
- immutable schema/metadata and update/delete trigger enforcement;
- missing, replaced-generation, foreign-schema, permissive-mode, and trigger
  drift rejection without auto-create;
- a busy writer returning indeterminate with no memory fallback;
- six independent connections racing the same request with exactly one winner;
- eight connections racing two scopes while preserving one immutable winner;
- four actual child processes racing with exactly one success;
- result loss after confirmed commit returning indeterminate, then replay;
- actual child-process SIGKILL after insert but before commit, followed by a
  clean first acceptance; and
- actual child-process SIGKILL after commit, followed by durable replay
  rejection.

Three ignored helper tests are invoked as separate OS processes by those parent
tests. The standard-library checker independently reconstructs the SQLite
schema, pins its exact SQL digest, and rejects 30 schema, trigger, type, length,
null, mutation, replacement, replay, and collision attacks.

S6, S5, S4, and S2 regressions remain gates. Store and Bridge default-off
builds remain gates, and Bridge is also checked with only the pre-existing S5
feature. All Cargo work uses one build job, disabled incremental compilation,
stripped debug information, offline locked dependencies, disabled default ONNX
features, and one test thread.

## What S7 does not establish

S7 establishes a synthetic local same-file at-most-once tombstone contract. It
does not establish:

- cross-repository or BioCortex transport;
- an authorized successor payload or resolved authority/key custody;
- a runtime/async receiver or cancellation behavior across an async worker;
- end-to-end exactly-once processing;
- protection against old-backup restore, file cloning/forking, multiple paths,
  same-UID transient DDL/data tampering, multiple hosts, or network-filesystem
  lock failures;
- universal power-loss durability;
- truth-manifest, candidate/final-context, `ast_` assertion, capture, producer,
  or live-ledger closure;
- privacy deletion or anonymous storage; or
- latency, throughput, memory, model-quality, BioCortex, neuroscience, or
  fermionic-algorithm gains.

The original five blockers remain unchanged:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

## Next admissible step

The next tranche should not attach S7 to Bridge. First choose and externally
record the authority/custody model for a genuinely new successor payload, and
choose an operational anti-rollback policy for the replay sidecar (monotonic
anchor or restore-bound key epoch). Only then may a separate default-off
receiver tranche add an async worker boundary with cancellation, restart, and
indeterminate-result tests. BioCortex influence remains a later independent
admission decision.
