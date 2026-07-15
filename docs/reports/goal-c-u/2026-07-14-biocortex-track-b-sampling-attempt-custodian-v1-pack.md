# BioCortex Track B sampling-attempt custodian v1 source pack

Date: 2026-07-14

Frozen source baseline: `c3a4ddce9ede20acf0cc90ef5d8c7e9c343d2245`

Decision: `LOCAL_CRASH_ATOMIC_CUSTODIAN_SOURCE_PROFILE_PASS_EXTERNAL_GLOBAL_SINGLE_USE_NOT_ADMITTED`

## Technical summary

This unit implements a local, crash-atomic reference custodian for the Track B
sampling-attempt lifecycle. It closes the local state-machine gap left by the
successor admission/map v1 pack: an owner-trial registration is committed
before a sampling-attempt namespace can be claimed, and each claim can acquire
exactly one immutable terminal outcome. The API workflow requires claim before
success evidence, but this local process cannot attest that an untrusted caller
did not obtain entropy or write elsewhere before calling claim. The
implementation and its three closed receipt schemas pass the deterministic
synthetic oracle and the directed self-test.

The result is deliberately **not** a production global custodian. A complete
SQLite database or VM snapshot can be restored to a pre-claim generation, and
the local process has no external owner-trust anchor or linearizable compare-
and-set service with which to detect that rollback. The test suite positively
reproduces this attack. Consequently every receipt keeps external owner trust,
external global single use, and condition-output authority false. The frozen
admission graph and live-binding ledger remain unchanged at 0 of 91 satisfied
bindings; no real owner registration, entropy, sampling receipt, condition
output, blind map, review, score, or unblinding artifact was created.

The state machine is:

`ABSENT -> REGISTERED -> CLAIMED -> TERMINAL_SUCCESS | TERMINAL_ABORT`

There is no update, delete, expiry, garbage-collection, alias, retry-after-
abort, or claimed-namespace release route. A failure after claim must become an
immutable `TERMINAL_ABORT`; it cannot make the namespace reusable.

The next source unit is a first-condition-output guard. That guard may consume
this local receipt profile for synthetic integration, but live admission must
remain blocked until a production owner-trust verifier and external anti-
rollback, globally linearizable custodian are bound.

## What this unit closes

### One exact registered tuple is consumed once

Registration binds all pre-entropy identity needed for a single sampling
attempt:

- `trial_id` intended for global use and its derived global trial key;
- protocol version and exact admission-policy digest;
- contract-core, eligible-frame, and strata-allocation digests;
- trial-only sampling-attempt namespace and exact sampling-event digest;
- owner authorization, owner freeze, and owner-trust-policy digests; and
- the pinned custodian generation, authority, instance, source, store schema,
  sampling-receipt schema, and sampling writer identities.

The local registration table uses unscoped `trial_id` as its primary key, not
`(protocol_version, trial_id)`. A protocol change therefore cannot reopen an
already consumed label inside that store. This is not proof of global
uniqueness across stores. The attempt namespace remains trial-only, while the
sampling event is rederived from the core, trial, frame, and allocation.
Claim begins with `BEGIN IMMEDIATE`, reads the exact registration tuple, and
requires the exact canonical registration-receipt digest before it inserts a
single namespace row and ledger event in the same transaction.

The claim receipt does not grant the next side effect. It says only that the
local namespace claim committed. In particular:

| Receipt fact | Value |
|---|---|
| `local_namespace_claim_committed` | `true` |
| `external_entropy_bound` | `false` |
| `live_sampling_write_authorized` | `false` |
| `external_global_single_use_verified` | `false` |
| `first_condition_output_guard_required` | `true` |
| `condition_output_authorized` | `false` |

### Terminal success and abort are a complete tagged union

The outcome request and receipt expose two mutually exclusive terminal
branches. The JSON Schema, Python validator, and SQLite `CHECK` constraint all
enforce the same branch rules.

| Branch | Required evidence | Forbidden evidence |
|---|---|---|
| `SUCCESS` | `COMPLETE_DURABLE_OBSERVED`, external entropy digest, exact canonical write-request bytes, and an open private receipt-directory descriptor | Caller-supplied receipt/observation objects, abort reason, and failure evidence |
| `TERMINAL_ABORT` | Non-complete write state, canonical abort reason, failure-evidence digest | Success-only write-request bytes or receipt-directory capability |

An abort may preserve the external-entropy and sampling-write-request digests
when they were already known. It never accepts success-only file evidence. It
is terminal and does not release the namespace.

For success, the caller can no longer submit receipt or observation objects.
The custodian hashes the exact write-request bytes, executes the hash-pinned
sampling writer against those bytes, and requires its rebuilt canonical receipt
to equal the single `sampling-receipt.json` leaf read through the supplied
directory descriptor. It verifies a user-owned `0700` directory, exact entry
set, a user-owned single-link `0400` receipt, inode stability, writer/schema and
trial/core/frame/allocation/entropy joins, selection commitment, exact
probability/weight grain, and false authority flags. It then re-reads and
`fsync`s the receipt and directory and derives the observation object and its
hash itself. The evidence scope remains local custodian replay/reread, not an external custody attestation.

### Data grain and join contract

| Surface | Logical grain | Physical uniqueness | Required join |
|---|---|---|---|
| Owner registration | Local registry generation × `trial_id` | `trial_id`, global-key candidate, namespace, event, owner authorization, owner freeze | Exact policy/core/frame/allocation/namespace/event and owner evidence; external global uniqueness remains false |
| Attempt claim | Local custodian instance × sampling-attempt namespace | Namespace primary key; trial, event, custody target, registration receipt unique | Exact canonical registration receipt and same full tuple |
| Terminal outcome | Local custodian instance × sampling-attempt namespace | Namespace primary key; trial, event, custody target, registration and claim receipts unique | Exact canonical claim receipt and same full tuple |
| Custodian ledger event | Local custodian instance × monotonic sequence | Sequence, request digest, receipt digest unique | One registration, claim, or outcome event in the same transaction as its row |

All request and receipt objects use canonical UTF-8 JSON with sorted keys,
two-space indentation, no non-finite numbers, no duplicate keys, and a final
line feed. Requests are closed field sets and bounded in size and nesting.
Derived identities are recomputed locally. Missing, extra, duplicate, null,
zero-sentinel, noncanonical, cross-trial, cross-event, cross-receipt, or
out-of-order values fail closed.

## SQLite durability and local security profile

Initialization is explicit and create-new only. Normal registration, claim,
outcome, and query calls refuse to create a missing store. The store is a
single-link regular file owned by the effective user with mode `0600` beneath
a user-owned `0700` directory with no symlinked ancestors. Initialization uses
`O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK`; runtime opening retains a
sentinel descriptor and rechecks file, pathname, `openat` leaf, and parent
identities before return.
Symlinks, hard links, special files, unsafe modes, unexpected SQLite sidecars,
identity changes, and configuration changes are rejected.

SQLite opens the already-created database with URI `mode=rw`; it never falls
back to pathname creation. The process confirms that an additional SQLite
descriptor is bound to the pinned database inode. Unsafe journal/WAL/SHM
sidecars are rejected before initialization/runtime open and after close.

The frozen SQLite profile is:

| Setting | Required value |
|---|---|
| Application ID | `1094861617` (`0x41424331`, ASCII `ABC1`) |
| User version | `1` |
| Journal mode | `DELETE` |
| Synchronous | `EXTRA` |
| Foreign keys | `ON` |
| Read uncommitted | `OFF` |
| Trusted schema | `OFF` |
| Locking mode | `NORMAL` |
| SQLite connection inode binding | Required |
| Pathname/openat rebinding check before return | Required |
| Store schema digest | `dd9980cf51c866c7a47f1c564f1ccd5faa38e2e684fa2c21ae6bcf9faccefa1f` |

The schema uses `STRICT, WITHOUT ROWID` tables, foreign keys, unique keys, and
no-update/no-delete triggers. Every mutation revalidates the application and
user versions, exact schema object catalog and SQL digest, pinned custodian
metadata, `quick_check`, and foreign-key integrity inside the write
transaction. Registration, claim, outcome row, ledger event, request bytes,
and generated receipt bytes commit atomically. The database file and parent
directory are `fsync`ed on durable close.

These controls provide the tested local crash boundary. They do not transform
the local filesystem into a remote trust authority and cannot detect a
coherent rollback of the database and its surrounding machine state.

## Scope and metric definitions

### In scope

- Append-only reference SQLite schema and explicit initialization profile.
- Owner registration, sampling-attempt claim, and one terminal outcome.
- Three closed JSON receipt schemas with exact source hashes.
- Exact tuple, canonical receipt, time-order, probability/weight, and durable-
  observation joins.
- Local process concurrency and pre/post-commit process-death behavior.
- Missing-store, symlink, FIFO, hard-link, permissions, application-ID, and
  schema-substitution negatives.
- Explicit reproduction of the unresolved whole-store snapshot rollback.
- Source-bound, descendant-compatible Git gate and frozen predecessor replay.

### Out of scope

- Verification that an owner authorization or freeze receipt was issued by a
  production trust root.
- An external monotonic generation, linearizable compare-and-set, transparency
  log, quorum, hardware counter, or other anti-rollback anchor.
- A real sampling run or independent custody attestation.
- Isolation from an untrusted process running under the same effective user;
  the local profile requires a dedicated custodian euid and private directory.
- Trusted-clock provenance, entropy unpredictability, or anti-shopping order.
- A first-condition-output interlock or any authority to expose conditions.
- Runtime Python, loaded-code, SQLite library, kernel, filesystem, or hardware
  provenance. The on-disk source digest is not a loaded-code attestation.
- Scientific, product, memory, retrieval, storage-efficiency, or biological-
  brain conclusions.

### Quantitative definitions before values

- **Directed mutation count** is the number of constructed invalid request,
  receipt, join, authority, and state vectors rejected by their intended
  validator. It is a test-vector count, not code coverage, statistical
  coverage, an error probability, or a proof that every invalid state is
  rejected.
- **Claim winner/loser count** is the observed result of six simultaneously
  released child processes attempting the same registered namespace in one
  deterministic synthetic test.
- **Outcome winner/loser count** is the observed result of two child processes
  racing success and terminal abort for the same committed claim.
- **Crash boundary count** is the six explicit `SIGKILL` injection positions:
  claim/outcome before commit, after commit but before the additional explicit
  file/directory `fsync`, and after that durable-close preparation.
- **Filesystem/schema rejection count** is the thirteen constructed local attacks,
  not a comprehensive operating-system threat-model coverage measure.
- **Unexpected-exception cleanup count** is one injected non-custodian
  `RuntimeError` before claim commit, followed by exact descriptor-set equality
  and a successful retry. It is not exhaustive exception or cancellation
  coverage.

| Synthetic diagnostic | Result |
|---|---:|
| Directed mutations rejected | 67 |
| Concurrent claim winners | 1 |
| Concurrent claim losers | 5 |
| Concurrent terminal-outcome winners | 1 |
| Concurrent terminal-outcome losers | 1 |
| `SIGKILL` transaction boundaries checked | 6 |
| Filesystem/schema attacks rejected | 13 |
| Unexpected-exception cleanup checks | 1 |
| Whole-store old-snapshot attack reproduced | Yes |
| Frozen live-ledger bindings satisfied | 0 of 91 |

No chart is used. These are categorical protocol test counts, not a measured
trend, distribution, throughput comparison, or effect magnitude; plotting
them as bars would imply a quantitative comparison they do not support.

## Methodology

### 1. Pin predecessor and design evidence

The manifest and Git gate pin the successor admission/map v1 packet, its v0/v1
runtime dependencies, and the S7 durable-replay and S9 external-authority
contract/source/report evidence by exact SHA-256. The current unit is append-
only and does not mutate the frozen admission policy, dependency graph, live-
binding ledger, or historical v0 route.

The gate runs the predecessor successor-pack gate first and requires its valid
integrated marker. It separately materializes historical commit
`59869af57f2a0b24647f3b47d7bea93839bfbefe`, replays the v0 checker there, and
requires its checked-in result byte-for-byte. This distinguishes historical
replay from current-source validation.

### 2. Build deterministic success and abort stores

The normal checker derives the synthetic v1 contract, frame, allocation,
attempt namespace, and event from the predecessor fixture. It creates a fresh
private store, registers the synthetic owner tuple, claims it, runs the pinned
sampling-receipt writer, and records success by passing the exact write-request
bytes and a private receipt-directory descriptor to the custodian. The
custodian independently replays the writer and derives the local observation.
A separate fresh store exercises terminal abort.
The reported success count and abort count therefore refer to two branch
fixtures, not two outcomes in one store.

The normal result is stable across `PYTHONHASHSEED=0` and `314159` and must equal
the checked-in TSV byte-for-byte.

### 3. Exercise mutations, concurrency, and process death

The self-test applies 67 directed mutations across schema shape, canonical
bytes, tuple identity, receipt joins, temporal order, outcome union, authority
escalation, probability/weight grain, durable-write observation, duplicate
claim/outcome, and configuration identity. Six spawned processes race the same
claim; exactly one transaction commits. Two processes then race success and
abort on one claim; exactly one terminal row commits.

Six child processes are killed at the named transaction/durability hooks. A
pre-commit kill leaves no visible row and permits the intended retry; both
post-commit positions retain the row and reject replay. The test also verifies
runtime missing-store noncreation and rejects a symlink, FIFO, hard link,
unsafe store mode, unsafe parent mode, application-ID drift, injected schema
object, unsafe initialization/runtime sidecars, post-open pathname replacement,
and a symlinked ancestor.

An additional hook raises an unexpected `RuntimeError` inside the claim
transaction. The operation rolls back and closes the SQLite, store, and parent
descriptors; the process descriptor set returns to its exact prior value and a
subsequent claim succeeds.

### 4. Test the limit rather than hiding it

The checker snapshots a valid pre-claim database, completes claim and terminal
outcome, then restores the old database image. The same claim is accepted again
and produces the same canonical claim receipt. This is expected and required
to remain visible as
`local_snapshot_rollback_attack_reproduced=true`. If this test stopped
reproducing without a newly bound external authority, the pack would reject
the unexplained claim rather than silently report stronger protection.

## Exact artifact identities

| Artifact | SHA-256 |
|---|---|
| Owner-trial registration receipt schema v1 | `98f6e2c539758c147d9c0d5050c88123f38e975539914e7e926421df10ac9eea` |
| Sampling-attempt claim receipt schema v1 | `baa08930421ca6c5a1e1e4835ad95e027b147592d3765371d0028956b96d1eb4` |
| Sampling-write outcome receipt schema v1 | `93d9b7ebda7f0fd6c24b1a1d0823866128db4885afe7f507b1ae8f6da7e4cb7d` |
| Custodian source | `29c410adef0c5d2b9b312e6417d507395bcb6d808140e8502eeb63211078c71b` |
| Purpose checker | `64ffc875a532a7ff0c76bfb5fbe947e3d6d8c7254f044793c9d5bfd0325f6848` |
| Synthetic fixture | `6dd66c46f60023b6b5bc301b800153c001503e2d6f449330d4a971da2bd78f29` |
| Expected normal TSV | `434c88d7ad50f9be6460b48c8a40b2cb19aaeb3043df8d7d53b194d150a359e9` |
| Pack manifest | `40c601c5f7ab45beb6cd497e6a1a274f2071c057fd1870c57b99c1d6fa7182c7` |
| Self-test output | `cfc787d3d40c12826a5b103316bfa96eff2e5f523fc1435dab2647aec0435165` |
| Source-bound Git gate | `f68974739e94a8794c96208d5978c52e411ba6388bac61b50f6009f3d7db419d` |

The receipt hashes in the checked-in normal oracle are deterministic synthetic
identities only. They are not live custody, owner trust, output authority, or
scientific evidence.

## Reproduction and interpretation

Run the purpose checker and directed self-test from the repository root:

```bash
python3 scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py
python3 scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py --self-test
```

After the source packet is committed, run the source-bound shell gate:

```bash
scripts/check-biocortex-ab-track-b-sampling-attempt-custodian-v1-pack.sh
```

On the source commit it must report a source-bound marker. On an ordinary
two-parent integration descendant it must report an integrated-valid marker.
Neither marker raises the false authority fields.

## Next decision

Proceed to
`FIRST_CONDITION_OUTPUT_GUARD_V1_SOURCE_PACK_WITH_EXTERNAL_AUTHORITY_STILL_REQUIRED`
only after this packet's independent data-quality, crash/concurrency, and Git-
gate reviews pass. The guard should require one exact terminal-success receipt,
the exact map/generation/output tuple, and an external live authority decision
before any first condition output. Until the external trust and anti-rollback
provider exists, it must remain a non-admitting source profile with all side
effects locked.
