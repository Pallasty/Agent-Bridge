# Free Recall Strategy R7 — Slice B Migration and Inert-Adapter Preregistration

Date: 2026-07-22

Status: **PREREGISTERED / DESIGN AND OFFLINE VALIDATION ONLY / NO SOURCE AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R6_SLICE_A_BUILD_RESULT_2026_07_22.md`

## 1. Question

R7 asks whether the next Slice B can be specified without accidentally
claiming a schema version, changing the default database, widening
`StateStore`, or opening a producer/retrieval path.

It validates a migration and inert-adapter contract only. It does not add SQL,
Rust, a feature, a database file, a producer, a build, or a runtime execution.

## 2. Current-source constraint

At preregistration time, `SqliteStore::open` finishes at schema version `43`.
That version is owned by `sqlite::temporal_evidence`, whose migration verifies a
canonical `sqlite_master` manifest and rejects unreviewed `truth_evidence.*`
metadata. The existing fusion-shadow relation is explicitly versionless because
it cannot advance that owner’s cursor safely.

Therefore R7 reserves neither `44` nor any other schema number. A Slice B
source gate must first name the then-current schema owner, the exact predecessor
cursor, the target cursor, and the owner-approved transaction/identity tests.
If that handoff is unavailable, source work stops. It may not copy the
fusion-shadow versionless pattern merely to bypass ownership.

## 3. Proposed relation

The only proposed relation is `episode_observation_events`:

```sql
event_id         TEXT    PRIMARY KEY,
episode_id       TEXT    NOT NULL,
event_type       TEXT    NOT NULL,
source_kind      TEXT    NOT NULL,
producer_run_id  TEXT    NOT NULL,
item_ref         TEXT,
episode_position INTEGER,
item_count       INTEGER,
payload_sha256   TEXT    NOT NULL,
observed_at      INTEGER NOT NULL
```

The real migration, if later authorized, must use these constraints:

- `event_type` is exactly `episode.open`, `episode.item`, or `episode.close`.
- `source_kind` is exactly `session`, `curation_batch`, or `owner_bundle`.
- `event_id`, `episode_id`, `producer_run_id`, and `payload_sha256` are
  non-empty UTF-8 text; `payload_sha256` is exactly 64 lowercase hex bytes.
- `observed_at >= 0`, `episode_position >= 0` when present, and `item_count >=
  0` when present; all three use SQLite integer values.
- Shape is exact: open has all item/count fields NULL; item has non-NULL
  `item_ref` and `episode_position` and NULL `item_count`; close has non-NULL
  `item_count` and NULL `item_ref`/`episode_position`.
- There is no foreign key to `memories`, no trigger, no FTS/vector/graph,
  no sync/export relation, and no retrieval-facing index. Beyond the primary
  key, the only index is `episode_id`.

`payload_sha256` authenticates a future public, content-free event envelope; it
does not make R7 a producer, serializer, or payload-retention authorization.

## 4. Migration contract

A future Slice B implementation must satisfy all of the following before it
may claim migration success:

1. It runs only from a named predecessor cursor under the current schema
   owner’s reviewed transaction protocol; it updates the cursor only after all
   DDL/identity checks succeed.
2. It is idempotent under two concurrent `SqliteStore::open` calls and leaves
   no partial table, index, or cursor advance after a collision/failure.
3. The relation is compiled only behind a new explicit default-off Slice B
   feature. A normal/default `ab-store` binary must neither create the relation
   nor alter `schema_meta`.
4. A feature-built but runtime-disabled store may own an empty inert relation;
   it must make zero producer calls, writes, reads, retrieval changes,
   sync/export changes, or public API changes.
5. New and upgraded *disposable* databases are the only migration test inputs.
   No user `state.db`, memory export, sync peer, or private capture is in
   scope.

The distinction in (3) and (4) is intentional: compile-time opt-in permits
schema preparation in an explicitly opted-in test binary, while runtime
default-off prevents observation behavior. A source gate must prove both.

## 5. Inert adapter boundary

The future adapter remains a private `SqliteStore` implementation detail. It
may provide exactly two internal operations:

- append one already-validated event; and
- read a finalized, internally validated episode projection.

It must not widen `StateStore`, expose MCP/API methods, infer episode
membership, derive `item_ref`, read raw memory keys, or call any producer. A
projection ignores an episode unless it has exactly one open, contiguous item
positions beginning at zero, exactly one close whose count matches the item
count, and no contradictory source/run identity. Missing, duplicate,
out-of-order, or malformed rows abstain.

The adapter has no caller in Slice B. The R5 candidate `session_curate`
producer remains Slice C and requires its own authorization.

## 6. Rollback and lifecycle

Rollback means disable the runtime gate and stop all future adapter callers;
the relation remains intact and inert. Existing rows are never rewritten.
Dropping a populated relation, partial deletion, backfill from `memories`, or
an erasure claim are separate destructive/lifecycle gates.

## 7. R7 offline gates

The R7 validator must reject directed mutations that:

- reserve a cursor, omit the schema-owner handoff, or use versionless DDL to
  evade it;
- create the relation under the default feature/runtime path;
- alter `MemoryRecord`, add a foreign key/trigger, or add FTS/vector/graph,
  sync/export, retrieval, or a public surface;
- weaken an event shape/value constraint or add an index beyond `episode_id`;
- widen the adapter, add a producer, infer membership, or finalize malformed
  episodes;
- drop/rewrite data during rollback, use non-disposable state, or claim any
  source/build/run/capture/retrieval/merge/deploy authority.

Object-key permutations must yield the same canonical report digest, and two
independent offline runs must be byte-identical.

## 8. Decision rule

If every R7 gate passes, the next possible request is narrowly for **Slice B
source only**: reviewed migration plus a private inert adapter. It does not
authorize Cargo resolution/build/test, producer wiring, runtime enablement,
real capture, retrieval, merge, deployment, or production key custody.

## 9. Negative authority

R7 does not authorize SQL/Rust source, feature changes, database access,
builds, tests against private state, producer calls, runtime configuration,
MCP/API work, retrieval, sync/export, key provisioning, merge, deployment,
training, or BioCortex.
