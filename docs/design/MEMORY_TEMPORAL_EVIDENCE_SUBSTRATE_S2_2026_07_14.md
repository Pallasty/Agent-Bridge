# Memory Temporal Evidence Substrate S2

Date: 2026-07-14

Status: **implemented for source-bound, synthetic-only verification; at most
`READY_FOR_SEPARATE_S3_ADAPTER_REVIEW`; no adapter or real capture authority**

Owner: Agent-Bridge memory plane

## Decision

S2 implements the storage mechanism preregistered in S1 without qualifying it
as a truth producer. It adds SQLite schema v43, a crate-internal append and
tombstone path that requires a test-only synthetic token, and a crate-internal
full-ledger snapshot reader. The implementation is deliberately unreachable
through `StateStore`, Bridge, MCP, or BioCortex.

This stage can prove that the five ledgers are created, identified, populated,
and read consistently under synthetic tests. It cannot prove that existing
`memories` rows are temporal evidence, that private data may be retained in an
append-only ledger, or that an operational owner has admitted an authority
policy. Its final decision remains `BLOCKED_FAIL_CLOSED`.

## Additive v43 migration

Writable store open advances only v42 to v43. It begins an immediate
transaction, re-reads the version after taking the lock, creates the five S1
tables, verifies that every new ledger is empty, records exact identity, and
commits. A v43 open re-verifies instead of recreating an assumed identity.

The new tables are:

| Table | Role |
|---|---|
| `truth_lineages` | immutable referent/predicate claim identity |
| `truth_authority_policy_revisions` | append-only predicate/source policy history |
| `truth_evidence_revisions` | complete immutable evidence envelopes |
| `truth_evidence_relationships` | revision-declared truth governance |
| `truth_lineage_tombstones` | permanent content-free deletion/governance attestations |

The migration adds six explicit indexes, ten raw `UPDATE`/`DELETE` rejection
triggers, and five insert guards. It does not scan or copy `memories`,
`memory_edges`, tags, aliases, `related_keys`, or `superseded_by`. A legacy row
surviving migration therefore contributes zero truth-ledger rows.

### Exact identity

Presence of a table is not accepted as schema identity. The verifier rebuilds
a canonical manifest from every persistent object whose name is in the
reserved `truth_*` or `idx_truth_*` namespaces, including an unexpected object
type. The scope also includes every non-autoindex object attached to one of the
five truth tables, even when its name is outside the reserved prefixes. This
prevents an innocently named trigger from changing writes without changing the
identity. The verifier similarly rejects reserved temporary objects and any
temporary object attached to a truth table, so a temp view or trigger cannot
shadow or mutate the reviewed behavior.

SQLite resolves identifiers case-insensitively. Manifest and temporary-object
selection therefore compare `lower(name)` and `lower(tbl_name)` to the reserved
lowercase scope; mixed-case names cannot escape identity checks. Every runtime
read and write outside the reviewed schema DDL is also explicitly qualified as
`main.truth_*`, providing a second boundary against temporary-schema shadowing.
These rules are bound in the v1 live-manifest label and migration digest.

The live manifest must equal the compiled schema SHA-256. The migration digest
separately binds the migration manifest, that schema digest, a DDL encoding
label, and the complete DDL bytes. `schema_meta` stores and the verifier checks:

- `truth_evidence.schema_sha256`;
- `truth_evidence.migration_sha256`;
- `truth_evidence.ledger_format_version`.

The entire `truth_evidence.*` metadata namespace is reserved. A v42 database
with any pre-existing key in that namespace is a migration collision. A v43
database must have exactly the three reviewed rows above; an unknown fourth key
is identity drift rather than ignorable metadata.

Writable open verifies the identity during migration/open. A generic
read-only store open retains its existing compatibility behavior; the new
internal snapshot verifies v43 identity inside the same read transaction
before returning evidence. Missing objects, added reserved objects, changed
SQL, changed metadata, disabled foreign keys, or foreign-key failures reject.

## Internal synthetic writer

The three write operations are inherent `SqliteStore` methods inside the
private SQLite module. Each requires `SyntheticTemporalEvidenceWriteToken`;
the only constructor is compiled under `cfg(test)`. No production caller can
mint that token in S2.

Each operation uses one immediate transaction, verifies producer identity,
applies local checks, inserts rows, reloads and validates the complete bounded
ledger, then commits. Failures return a typed internal error with a stable code
and roll back the whole transaction. Tests assert the code and category rather
than parsing display text.

The policy writer allocates a contiguous revision sequence, preserves
predicate/source identity, rejects parallel policy-lineage tier shopping, and
requires strictly increasing knowledge time. Evidence admission atomically
creates its lineage on the first revision, then enforces:

- immutable referent/predicate identity and contiguous store allocation;
- canonical value, aliases, provenance, validity, lifecycle, and relationship
  encodings;
- `observed_at <= recorded_at` and strictly increasing lineage knowledge time;
- exact latest-visible, active predicate/source authority policy, with the
  tier derived by the store;
- complete relationship carry-forward;
- closed, same-claim, non-self endpoints and no cycle among latest revisions;
- target authority from the target revision recorded strictly before the
  source, with same-second ambiguity and lower-tier suppression rejected;
- relationship effective time inside source activity.

A tombstone requires an existing revision, blocks future source revisions,
and derives both `had_outgoing_governance` and its attestation digest. Historical
or later inbound references to a tombstoned target remain in the substrate;
pruning is an adapter decision. A tombstoned source may retain historical
outgoing governance, but cannot append new evidence.

Raw insert triggers are defense in depth, not a substitute for the internal
writer. Raw `UPDATE` and `DELETE` on all five tables reject.

## Complete snapshot reader

The internal reader opens one deferred read transaction, verifies v43 identity,
performs byte preflight before decoding, and returns all five complete ledgers
in binary canonical order. It binds producer identity, ledger format, caller
limits, exact counts, canonical payload bytes and SHA-256, and a caller-supplied
`knowledge_cutoff`.

The cutoff is metadata for a later projector; it does not filter the substrate
snapshot. A revision recorded after the cutoff must still appear in the full
ledger. This prevents a partial snapshot from being mistaken for complete
history.

Configured count caps are fetch-plus-one sentinels: `count >= cap` rejects, so
the largest accepted count is `cap - 1`. Canonical payload bytes likewise
reject at `bytes >= max_payload_bytes`. A request may lower, but not exceed,
the S1 maxima:

| Bound | Maximum permitted configuration |
|---|---:|
| lineages | 10,000 |
| policy revisions | 10,000 |
| evidence revisions | 10,000 |
| relationships | 50,000 |
| tombstones | 10,000 |
| payload bytes | 16,777,216 |

Canonical payload generation streams directly into a bounded SHA-256 writer.
The writer rejects before a write would reach the byte sentinel; it does not
materialize a second full-ledger byte vector. Snapshot structs keep their
serialized fields in canonical binary key order, with the frozen S1 9,566-byte
payload and digest as an exact regression. Cycle validation likewise uses an
explicit DFS stack rather than call-stack recursion, including the largest
reachable 9,999-lineage chain below the strict lineage sentinel.

Capacity, decode, canonicalization, closure, sequence, policy, relationship,
tombstone, digest, or schema failure is terminal. The reader never silently
truncates or repairs a row.

## Boundary deliberately preserved

S2 does not change `MemoryEvidenceProfile::MutableSqliteV41` or
`memory_truth_adapter`. The existing mutable producer therefore continues to
report exactly eight gaps:

1. complete lineage revision history unavailable;
2. unique lineage revision order unavailable;
3. complete tombstone governance index unavailable;
4. all relationship channels and history unavailable;
5. relationship endpoint closure unprovable;
6. durable governance attestation unavailable;
7. explicit temporal claim/provenance bindings unavailable;
8. predicate-scoped authority policy unavailable.

The new snapshot cannot enter the adapter, projector, Bridge, MCP, or BioCortex.
No producer-profile name is reserved or promoted. S3 must separately review a
producer-bound adapter and resolve how read-only identity, custody, deletion,
and projection failure semantics cross that boundary.

Append-only raw evidence also remains incompatible with an unreviewed promise
of physical privacy deletion. Real/private capture stays blocked until content
separation, cryptographic erasure, or another owner-approved mechanism is
implemented and tested. Authority-policy custody is likewise unresolved: S2
tests mechanism, not who may approve real policy.

## Synthetic controls

The public fixture uses invented identifiers only. It records one legacy row
remaining unqualified across v42-to-v43, two policies, three lineages, four
evidence revisions, two carried-forward relationships, and one content-free
tombstone. Its cutoff is 160, while revisions recorded at 180 and 350 remain in
the full snapshot. The inbound relationship to the tombstoned target is also
retained.

Rust tests with the `truth_evidence_s2_` prefix cover migration and no-backfill,
exact identity tampering (including a non-reserved trigger attached to a truth
table), writer/snapshot round trips, transaction rollback,
policy visibility, relationship time/tier/cycle/carry-forward controls,
tombstones, append-only enforcement, case-variant temporary shadow rejection,
deep iterative cycle validation, streaming cap enforcement under JSON control
character expansion, deterministic digest, and read-only snapshot
verification. Only the `ab-store` library is built, with default ONNX features
disabled and one build/test job.

## Source-bound acceptance

After the S2 tranche is committed and the worktree is clean, run:

```bash
./scripts/check-memory-temporal-evidence-substrate-s2.sh
```

The gate requires integration commit
`1c1770579c46f325ef4a1dee3f870bfe20a5a09a` (S1 plus the independently merged
Track B artifact-dependency graph) as an ancestor and permits only the five S2
implementation/lock/test files plus the seven new packet files to differ from
it. It materializes `HEAD` with `git archive`, runs the standard-library
checker twice under a sanitized environment, compares both receipts to the
fixed TSV, then runs the filtered Rust tests offline with `CARGO_BUILD_JOBS=1`,
`CARGO_INCREMENTAL=0`, `-j 1`, `--no-default-features`, and one test thread.

The checker pins all seven S1 packet hashes and the complete
`memory_truth_adapter.rs` hash, including its eight-gap test. The report binds
the S2 packet, Rust module and tests, SQLite integration, manifest, and lockfile
hashes.
The gate fences `HEAD`, index, and worktree state before and after execution.

A PASS establishes only the S2 storage mechanism and raises the maximum status
to `READY_FOR_SEPARATE_S3_ADAPTER_REVIEW`. The receipt still says
`store_adapter_present=false`, `legacy_rows_qualified=false`,
`real_capture_authorized=false`, `biocortex_runtime_influence=false`, and
`decision=BLOCKED_FAIL_CLOSED`.
