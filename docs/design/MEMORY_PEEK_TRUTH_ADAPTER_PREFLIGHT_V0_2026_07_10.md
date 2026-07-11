# Memory Peek and Truth-Adapter Preflight v0

Date: 2026-07-10
Status: implementation contract — read-only diagnostic, adapter blocked
Owner: Agent-Bridge memory plane

## Decision

Temporal Truth Projection v0 now has a deterministic pure resolver, but the
live memory store cannot yet supply its input contract. The next safe slice is
therefore diagnostic only:

1. add an exact `memory_peek` read that does not alter access or retrieval
   telemetry;
2. read a bounded retained-row/tombstone/edge metadata inventory in one SQLite
   read transaction;
3. run a crate-private completeness preflight that must reject the current
   store before any row can reach the projector.

This slice does not add an MCP tool, search mode, ranking path, database schema,
runtime flag, BioCortex transport, or truth-evidence mapping.

## Why the current store is not admissible

The live SQLite schema is useful memory storage, not an immutable evidence
ledger:

- `memory_save` upserts one mutable row per key; earlier content, lifecycle,
  tag, source, and relationship revisions are overwritten;
- `created_at`/`updated_at` are not a unique per-lineage revision order;
- tombstones can be physically purged, with no permanent content-free deletion
  or governance attestation;
- relationship facts are distributed across `memory_edges`, `related_keys`,
  `superseded_by`, and continuity tags;
- edge endpoints are not protected by a foreign key and a declared supersede
  may name a target that does not yet exist;
- `MemoryRecord` does not contain explicit referent/predicate identity,
  observed/recorded time, temporal validity, or predicate-scoped truth
  authority.

Backfilling the current row as if it were complete history would manufacture a
false guarantee. Legacy rows remain unqualified even after a future append-only
ledger exists, unless they undergo a separate explicit admission process.

## Exact-read contract

`StateStore::memory_peek(key)` has three outcomes:

- `present`: exact current active, archived, superseded, or conflict row;
- `tombstoned`: key plus `updated_at` marker only;
- `missing`: no retained row.

It must not change:

- `access_count` or `last_accessed_at`;
- `memory_query_log`;
- `retrieval_surfacing` or used-attribution fields;
- `memory_coactivation`;
- any other SQLite change counter.

It can run through `SqliteStore::open_read_only`. Tombstoned content, tags,
scope, and relationships are not selected or returned. `memory_peek` is an
internal diagnostic primitive, not a quieter retrieval API; it must not be
registered in MCP or used for ordinary recall.

The exact decoder fails closed on malformed tag/relationship JSON, negative
access counters, invalid importance, or unknown lifecycle status. It does not
silently repair damaged evidence into a plausible record.

## Evidence-snapshot contract

`StateStore::memory_evidence_snapshot(limits)` reads, in one deferred SQLite
read transaction:

- non-tombstoned retained current row markers (`key`, lifecycle status,
  `created_at`, `updated_at`), ordered by key;
- content-free tombstone markers, ordered by key;
- visible edges including `created_at`, ordered by source, target, and type.

Every category is caller-bounded and hard-capped. A separate aggregate UTF-8
payload-byte ceiling is enforced before Rust allocates each selected string;
container overhead is independently bounded by the row caps. The
implementation fetches one extra row to set `truncated`; row or byte truncation
blocks admission. A direct retained-endpoint closure check is reported, but
passing it does not prove full relationship closure because `related_keys`,
continuity tags, supersede fields, and purged history remain outside the
inventory.

Edges incident to a retained tombstone are excluded so deletion cannot
rehydrate its relationship endpoints or types; the snapshot reports only that
such relationships were redacted, which independently blocks admission.
Retained content, tags, scope, and `related_keys` stay behind single-key
`memory_peek` and are never bulk-loaded here.

The snapshot is opaque outside `ab-store`, has private payload fields, and does
not implement serde. It must not leave Agent-Bridge or be sent to BioCortex.
Only the aggregate preflight result is serialization-safe for later review
surfaces, and that report is output-only rather than a deserializable admission
token.

## Completeness preflight

The crate-private preflight requires all of these:

1. exact reads are side-effect free;
2. all adapter reads share one snapshot;
3. no cap was exceeded;
4. the exact snapshot contains complete immutable lineage revision history;
5. lineage revision order is unique in that snapshot;
6. the exact snapshot contains a complete tombstone/governance index;
7. all relationship channels and their history are present, endpoint closure
   is provable, the retained view has no dangling endpoint, and no tombstone
   relationship had to be redacted;
8. deleted governance sources retain a durable content-free attestation;
9. explicit claim identity, observed/recorded/validity time, and source
   provenance bindings exist;
10. truth tier comes from an Agent-Bridge predicate-scoped authority policy.

Missing any condition produces a canonical `TruthAdapterGap` and
`adapter_allowed=false`. Current SQLite is expected to pass only conditions 1
and 2. A preflight failure is terminal for the adapter request: it must not be
converted to `unknown`, and the projector must not be invoked.

Capabilities are not caller-supplied booleans. The opaque snapshot carries a
non-deserializable producer/schema profile set by `ab-store`; the bridge maps
that reviewed profile to the guarantees the implementation can actually make.
The only current profile is mutable SQLite v41 and cannot be made admissible by
constructing a synthetic all-true value.

`MutableSqliteV41` is currently a conservative implementation label, not a
schema attestation. Before any future profile can map to an admissible fact
set, writable and read-only opens must bind it to a verified schema version and
migration/hash identity.

## Acceptance gate

The slice is accepted only when tests prove:

- repeated peek leaves access/query/surfacing/coactivation and SQLite total
  changes byte-for-byte unchanged;
- a positive-control `memory_get` trips the same mutation probe;
- a read-only connection can peek retained rows;
- tombstoned and missing results expose no tombstoned content or relationship;
- malformed exact envelopes fail closed instead of being normalized;
- the evidence inventory is deterministic, row/byte bounded, and zero-write;
- a concurrent WAL writer cannot change later reads inside the same deferred
  read transaction;
- timestamped visible edges and dangling retained endpoints remain visible;
- row truncation, byte truncation, and invalid limits fail closed;
- read-only snapshots work and redact tombstone-incident edges;
- the producer-bound current SQLite profile always yields
  `adapter_allowed=false`;
- the private evaluator admits only an artificial complete fact set used by
  unit tests; no current store profile can produce it;
- the serialized preflight contains no memory record, key, content, tombstone,
  or edge material;
- no MCP registry/default profile or BioCortex repository changes.

## Later admissible path

A real adapter requires an append-only evidence revision ledger, a permanent
content-free tombstone/governance ledger, explicit claim/time/provenance and
authority bindings, and one bounded snapshot reader containing all lineage and
relationship channels. Those additions need their own schema and migration
review. They are not authorized by this diagnostic slice.
