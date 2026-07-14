# Memory Temporal Evidence Substrate S1

Date: 2026-07-14

Status: **design preregistration ready for separate schema/migration review;
no migration, writer, adapter, projector call, or runtime authority**

Owner: Agent-Bridge memory plane

## Decision

The next Track B unit is a logical evidence-substrate contract, not a database
migration. S0 made the retrieval reference deterministic, but the mutable
`memories` store still lacks the eight evidence-completeness guarantees recorded
by `memory_truth_adapter`. S1 freezes the smallest independent ledger design and
tests it with public synthetic rows before any persistent schema is approved.

The machine-readable contract is
`scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_contract_v0.json`.
Its lower-level schema is intentionally Agent-Bridge-owned and does not use a
BioCortex namespace. BioCortex receives no read, write, ranking, transport, or
runtime authority from this design.

## Non-authority boundary

S1 does not:

- alter SQLite or reserve a schema version or producer-profile name;
- add a writer, snapshot reader, store adapter, MCP surface, or runtime flag;
- invoke Temporal Truth Projection or qualify a mutable memory as evidence;
- backfill a legacy memory row, tag, edge, `superseded_by` field, or tombstone;
- open the owner store, BioCortex, a model, or a private corpus;
- authorize capture, generation, review, unblinding, score, deployment, or a
  scientific/performance claim.

The public fixture is invented mechanism data. Its `adapter_allowed=false`,
`real_capture_authorized=false`, and final decision is `BLOCKED_FAIL_CLOSED`.

## Logical ledger design

The future migration review receives five append-only logical ledgers. Their
names and fields are frozen by the JSON contract, while physical SQL, indexes,
triggers, encryption, and the next schema version remain review decisions.

| Ledger | Purpose | Load-bearing rule |
|---|---|---|
| `truth_lineages` | Immutable `(referent_id, predicate_id)` identity | A memory key is never a referent; claim identity cannot change after creation. |
| `truth_authority_policy_revisions` | Versioned predicate/source authority policy | Unknown predicate/source pairs reject; the evidence caller cannot assign a tier. |
| `truth_evidence_revisions` | Full immutable evidence envelopes | Every material change appends a complete new revision; no update or delete. |
| `truth_evidence_relationships` | The sole truth-governance relationship channel | Rows bind the declaring evidence revision, target lineage, kind, and effective time. |
| `truth_lineage_tombstones` | Permanent content-free deletion/governance index | The store derives whether the deleted lineage ever had outgoing governance. |

The declared primary keys, foreign keys, and store-derived fields are
load-bearing parts of this design rather than illustrative SQL hints. Removing
or weakening any of them requires a design-version change and must be rejected
by the public contract checker.

The future append transaction must be one store-owned immediate transaction.
It allocates `revision_seq`, resolves `truth_tier` from an already admitted
policy revision, checks the complete envelope and relationship endpoints, then
commits all-or-nothing. Raw `UPDATE` and `DELETE` on these ledgers must be
rejected. A tombstone blocks every future revision and outgoing relationship
for its lineage.

## Revision and clock contract

Each lineage starts at `revision_seq=1` and advances without a duplicate or
gap. Sequence is explicit because Unix-second timestamps alone cannot order two
admissions in one second. Temporal Truth Projection v0 nevertheless still
requires a unique `recorded_at` within each lineage. S1 therefore requires both:

- contiguous, store-allocated `revision_seq`; and
- unique monotonically increasing `recorded_at` for resolver-v0 compatibility.

S1 explicitly forbids pretending that a sequence can be converted into an
invented second. Supporting legitimate same-second revisions requires a later
resolver-v1 contract.

The clocks remain distinct:

- `observed_at`: world time at which a source observation occurred;
- `recorded_at`: knowledge time at which Agent-Bridge admitted the immutable
  envelope;
- `valid_from`/`valid_until`: inclusive world-time validity bounds;
- lifecycle and relationship `effective_from`: inclusive transition times.

Late backfill is retained in the ledger but must be invisible to a knowledge
view whose cutoff precedes its `recorded_at`.

## Claim, provenance, and authority

A lineage owns one explicit `referent_id + predicate_id`. Each revision binds
at least one canonical Agent-Bridge source identity and provenance digest.
Neither free text, a tag, importance, similarity score, caller boolean, nor
memory kind can create claim identity or authority.

An evidence revision references a particular authority-policy revision. The
store joins the lineage predicate and source identity to that policy and derives
the stored tier. Missing, revoked, future, expired, predicate-mismatched, or
source-mismatched policy revisions reject the whole append. Default authority
is rejection, not `inferred`.

Policy revision history is itself append-only and knowledge-time bound. Within
one policy lineage, `predicate_id` and `source_key` are immutable,
`revision_seq` is contiguous, and `recorded_at` must increase strictly with the
sequence. Exactly one policy lineage may own a given predicate/source pair; a
parallel active lineage cannot be used to shop for a more favorable tier.

For an evidence admission at `recorded_at=t`, the store selects the latest
policy revision in that lineage visible at `t`. The evidence must bind that
exact revision, and it must be active and valid at `t`. A later visible
revocation therefore blocks admission; the writer may not fall back to an older
revision whose row still says `active`. S1 does not specify who may approve a
real policy; that owner/custody decision belongs to the later migration and
adapter reviews.

## Relationship completeness

Truth relationships have only two v0 kinds: `supersedes` and `invalidates`.
They target a lineage and name the exact evidence revision that declared them.
Every evidence revision is a full relationship snapshot. Once declared, a
relationship must be carried forward by later revisions of the source lineage.

The future writer and snapshot reader must reject:

- missing, self, or cross-claim endpoints;
- cycles;
- two kinds or two effective times for the same source/target declaration;
- a relationship outside the source's active validity/lifecycle interval;
- a lower authority tier suppressing a higher tier;
- a later revision that drops a durable relationship.

The authority comparison is knowledge-time scoped: the target tier is taken
from the target lineage's latest revision recorded strictly before the
declaring source revision's `recorded_at`, not from a globally latest or later
downgraded target. A subsequent target downgrade cannot retroactively make an
earlier relationship admissible. Because v0 has no global admission sequence,
any target revision in the same timestamp second as the source is ambiguous and
the relationship must reject; resolver v1 is required to admit that case.

The dedicated relationship ledger becomes the only admissible truth channel.
Legacy `memory_edges`, `related_keys`, tags, and `superseded_by` remain ordinary
memory metadata and cannot be silently merged into it.

## Tombstone and privacy contract

A truth tombstone is permanent and content-free. It retains only the lineage,
time, format version, a store-computed `had_outgoing_governance` bit, and an
attestation digest. Value, content, aliases, and source payload are forbidden.

An inbound relationship whose target is tombstoned may be pruned from a
projection. A tombstoned source that ever declared outgoing governance is
different: silently deleting the correction could resurrect its target, so the
adapter must fail closed. The synthetic fixture includes both cases.

Append-only raw values and physical privacy deletion are in tension. S1 does
not resolve that tension or authorize real/private data. The migration review
must choose a separately reviewed mechanism such as content separation with
cryptographic erasure, while retaining only the minimum content-free governance
attestation. Until then, the ledger is synthetic-only.

## Snapshot contract

A future admissible snapshot reads all five ledgers in one SQLite read
transaction. Each category and total canonical payload bytes has a hard cap and
uses fetch-plus-one. Any truncation, incomplete tombstone index, missing
relationship channel, endpoint non-closure, decode error, or noncanonical order
is terminal.

S1 freezes these design maxima:

| Bound | Maximum |
|---|---:|
| `max_lineages` | 10,000 |
| `max_policy_revisions` | 10,000 |
| `max_evidence_revisions` | 10,000 |
| `max_relationships` | 50,000 |
| `max_tombstones` | 10,000 |
| `max_payload_bytes` | 16,777,216 |

An implementation may choose a lower request bound, but never a higher one.
Changing any maximum requires a new evidence-substrate design version; it
cannot be treated as a runtime configuration change.

The snapshot binds:

- actual `schema_meta.version`;
- reviewed schema digest;
- reviewed migration digest;
- ledger format version;
- canonical binary ordering and canonical payload SHA-256;
- all row counts, caps, and the knowledge cutoff.

The current `MutableSqliteV41` name is a conservative implementation-profile
label, not an attestation of the repository's current schema version. S1 does
not rename it or infer a future profile merely because tables may later exist.
Writable and read-only opens must both verify the eventual identity before a
new producer profile can be reviewed.

## Synthetic controls

The public fixture covers:

- two immutable revisions in one lineage plus relationship carry-forward;
- unique sequence and resolver-v0-compatible recorded times;
- observed/recorded clocks and a late backfill beyond the knowledge cutoff;
- the same referent with three distinct predicates;
- inclusive scheduled supersession immediately before and at its boundary;
- explicit invalidation;
- a same-tier conflict and lower-tier evidence derived from policy bindings;
- latest-visible policy selection, revocation blocking, strict policy time
  order, and predicate/source anti-shopping identity;
- relationship authority evaluated against the target revision visible at the
  declaring source's knowledge time, including later-target-downgrade and
  same-second-ambiguity guards;
- tombstoned inbound-target pruning;
- a content-free tombstoned governance source that keeps the adapter blocked;
- a bounded, complete, canonical synthetic snapshot under the six frozen
  design maxima.

The checker also mutates and rejects 36 preregistered adversarial cases. In
addition to sequence ambiguity, claim drift, relationship failures, authority
laundering, time inversion, governance-attestation loss, tombstone leakage,
truncation, hash/order drift, unknown fields, and duplicate JSON keys, the set
explicitly covers primary-key, foreign-key, and store-derived-field contract
drift; policy revocation bypass, policy-time regression, and tier shopping;
later and same-second target downgrades; and an unbounded snapshot cap.

This checker validates design consistency only. It deliberately does not call
the existing projector, whose behavior already has its own Rust tests.

## Acceptance and next stage

Run after committing from a clean worktree:

```bash
./scripts/check-memory-temporal-evidence-substrate-s1.sh
```

A PASS means `design_status=READY_FOR_SEPARATE_MIGRATION_REVIEW`, while all
runtime/admission booleans remain false. S1 is complete only when the design,
contract, fixture, expected receipt, checker, gate, and report are source-bound
and two checker executions are byte-identical.

The next stage is S2: a separately reviewed additive migration plus internal
append/tombstone writer and complete snapshot reader, initially synthetic-only.
S2 must preserve the existing mutable-profile eight-gap rejection. S3 may then
review a producer-bound store adapter. A new Track B admission packet comes
after those stages; the old v0 packet is never edited to inherit new source
hashes.
