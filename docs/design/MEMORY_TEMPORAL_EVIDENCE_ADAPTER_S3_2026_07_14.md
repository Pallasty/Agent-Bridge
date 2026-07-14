# Memory Temporal Evidence Adapter S3

Date: 2026-07-14

Status: **`PREREGISTERED_BLOCKED_PENDING_S4_INTERFACE`; no adapter, producer
profile, projector call, real capture, or runtime effect**

Owner: Agent-Bridge memory plane

## Decision

S3 does not implement the anticipated S2-to-projector adapter. Source review
found one semantic P1 incompatibility and four additional interface integrity
gaps. Mapping the new SQLite v43 ledger directly into
`TruthProjectionRequest v0` would change the authority semantics of already
admitted relationships and would lack the provenance, read-only identity, and
sealed result boundary required for a trustworthy adapter.

The S3 artifact is therefore a fail-closed preregistration for a separate S4
interface. It binds the exact S2 mechanism, projector v0, legacy preflight, and
Track B dependency graph; records six invented counterexamples; and rejects 28
hostile packet mutations. Rust remains byte-identical to the S2 baseline.

`BLOCKED_FAIL_CLOSED` is the only admission decision produced by this stage.

## Why a direct adapter is unsafe

### 1. An independent content-free tombstone channel is absent from v0

S2 stores a tombstone in its own ledger with only tombstone identity, lineage,
time, the `had_outgoing_governance` bit, and attestation identity. The complete
S2 snapshot also retains the lineage's historical revisions because the v43
ledger is append-only.

Projector v0 represents deletion as `LifecycleState::Tombstoned` inside a full
`TruthEvidence`. Its request has only `required_claims` and `evidence`; there is
no independent tombstone collection. A mapper can technically reuse a retained
revision to fill that envelope, so this is not a current representability P1
and does not require fabricated content. It does, however, re-carry logically
deleted values and sources into the projector, cannot preserve the tombstone
id/attestation/governance bit as a first-class input, and ceases to work if the
future privacy mechanism physically or cryptographically erases revision
content.

The independent channel is therefore a data-minimization, audit, and forward
privacy requirement for S4. A tombstoned lineage that had outgoing governance
is stricter: S4 must reject the complete snapshot before mapping. An inbound
edge whose target is tombstoned may be pruned from an attested tombstone marker
without synthesizing a new evidence envelope.

### 2. Relationship authority uses different knowledge times

S2 admits and revalidates a relationship using the target's latest revision
recorded strictly before the source revision's `recorded_at`. A target revision
in the same second is ambiguous and rejected. This is a normalized full-ledger
source-time rule, not a persisted witness of physical insert order: v43 permits
a later physical append whose target `recorded_at` backfills an earlier point,
then revalidates the complete ledger.

Projector v0 selects the latest target visible at the request's
`knowledge_cutoff`, then compares its tier with the source tier. A later target
upgrade can consequently make a previously legal relationship fail; a naive
representation of previously rejected data could have the inverse laundering
effect after a later downgrade. The S3 fixture makes the first counterexample
explicit: a verified source legally suppresses an observed target at time 100,
then projector v0 sees an authoritative target revision recorded at time 200
and rejects the old relationship at cutoff 250.

S4 must deterministically derive from the complete validated snapshot the
latest target strictly before the source time, then bind that source id/time
and exact target id/revision/time/tier in the prepared input. The projector must
not re-decide authority from the cutoff-latest target tier. S3 does not claim
this derived object reconstructs the original physical admission decision; if
that audit property is later required, the store schema must persist an
immutable admission witness or global append sequence.

### 3. Provenance digests disappear in v0

Every S2 source binding is `(source_key, provenance_sha256)`. Projector v0
retains only `source_keys`. An aggregate snapshot digest proves the bytes of a
complete snapshot but cannot replace the evidence-to-provenance relation that
downstream audit needs. S4 must preserve both fields without lossy mapping.

### 4. Read-only producer identity is not yet unforgeable

The v43 reader, snapshot type, and synthetic writer token remain private to the
SQLite module. That is the safe S2 boundary, but it means no cross-crate object
currently proves that a specific snapshot came from an actual read-only,
query-only open which verified the v43 schema, migration, caps, counts, and
canonical payload in one transaction. A caller boolean or trusted-sounding
profile name is not such proof.

### 5. Projection is not sealed to its snapshot

`TruthProjection` has no producer identity, snapshot digest, mapping version,
prepared-input digest, or projection digest. Returning a mutable
`TruthProjectionRequest` next to a separate receipt would permit substitution
or replay. Projector v0's own module comment already reserves sealed snapshot
binding for a later boundary.

S4 must perform mapping and projection atomically and return a single immutable
result envelope bound to the exact producer identity and full snapshot.

## Frozen S3 gaps

The machine contract records five interface gaps and five operational/admission
gaps in one sorted ten-code set:

| Code | Class | Why it blocks |
|---|---|---|
| `CONTENT_FREE_TOMBSTONE_CHANNEL_UNREPRESENTED` | interface/data minimization | v0 can re-carry retained content but cannot carry the independent tombstone attestation |
| `RELATIONSHIP_SOURCE_TIME_AUTHORITY_BASIS_UNREPRESENTED` | interface P1 | v0 recomputes target tier at cutoff instead of using S2's strict-before-source full-ledger rule |
| `PROVENANCE_DIGEST_CHANNEL_UNREPRESENTED` | interface | v0 drops each S2 provenance digest |
| `READ_ONLY_OPEN_IDENTITY_UNBOUND` | interface | no immutable cross-crate read-only producer proof exists |
| `SEALED_SNAPSHOT_PROJECTION_BINDING_UNREPRESENTED` | interface | result can neither prove nor seal its complete input snapshot |
| `CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED` | integration | Track B's candidate evidence interface remains absent |
| `PRODUCTION_PRODUCER_PROFILE_UNADMITTED` | admission | no profile is reserved or promoted by S3 |
| `CAPTURE_PROVENANCE_UNATTESTED` | governance | mechanism bytes do not prove who supplied or authorized data |
| `AUTHORITY_POLICY_CUSTODY_UNRESOLVED` | governance | synthetic policies do not appoint a real policy custodian |
| `PHYSICAL_PRIVACY_DELETION_UNRESOLVED` | governance | append-only content has no approved physical/cryptographic deletion mechanism |

These codes describe different evidence obligations. In particular, a capture
receipt cannot substitute for a sealed projection binding, and a snapshot
digest cannot substitute for per-evidence provenance.

## S4 minimum interface

S4 should add a parallel projection v1 rather than silently changing v0.
Before any production profile review, its internal shape must provide:

1. An unconstructable, non-`Deserialize`, field-private read-only v43 snapshot
   with immutable getters. The producing operation verifies `query_only`, exact
   schema/migration/ledger identity, full-ledger counts and caps, and payload
   digest in one transaction. It must not be a default `StateStore` method.
2. A crate-internal, non-serializable `PreparedTemporalEvidenceV1` containing
   the complete ledger, including revisions after the projection cutoff.
3. An independent `TruthTombstoneV1` channel with exactly tombstone id, lineage
   id, time, outgoing-governance bit, and attestation version/digest. Evidence
   v1 must not have a tombstoned lifecycle variant.
4. Lossless source bindings containing `source_key` and
   `provenance_sha256`.
5. A relationship source-time basis derived from the complete validated ledger
   and bound to the exact strict-before target revision and snapshot digest.
   It is not represented as an original physical-admission witness. Same-second
   targets remain rejected.
6. One `project_bound(snapshot, as_of, required_claims)` operation. It does not
   expose a prepared request. Its immutable result binds producer identity,
   payload SHA/bytes/counts/limits/cutoff, mapping version, prepared-input SHA,
   request time, projection SHA, and pruned counts.

A mechanism profile name may describe only the mechanism, for example a
read-only SQLite v43 ledger format. It must not imply trusted data, owner
approval, production status, or authority-policy custody.

If an eventual result crosses into BioCortex, raw ids, values, and source keys
must be replaced by request-scoped opaque handles bound with a nonce/HMAC. Raw
truth material may not be persisted or forwarded over the network by that
boundary.

## Full-ledger and failure rules

The adapter must receive the complete bounded S2 ledger. It may not remove
post-cutoff revisions before projection because those bytes are part of the
snapshot identity and are needed to prove that cutoff selection did not alter
input completeness. Any identity, cap, count, digest, provenance, witness,
tombstone, or binding mismatch terminates the entire operation.

The synthetic fixture freezes six cases:

1. exact schema identity without capture, custody, or deletion authority;
2. a content-free tombstoned inbound target that S4 may prune;
3. a content-free tombstoned governance source that S4 must reject;
4. a target tier upgrade after the source knowledge time;
5. a post-cutoff revision retained in the full ledger; and
6. a projection from snapshot A falsely paired with snapshot B.

The fixture contains invented identifiers and digests only. It is not evidence
of real capture, performance, privacy compliance, or scientific effect.

## Boundaries preserved

S3 does not:

- change `memory_truth.rs`, `memory_truth_adapter.rs`, store code, or Cargo
  metadata;
- reserve or activate a producer profile;
- expose the temporal reader through `StateStore`, Bridge, or MCP;
- invoke projector v0 or construct a truth request;
- qualify legacy `memories` rows;
- rewrite the Track B graph, live-binding ledger, or real-run admission;
- authorize private capture, policy custody, or physical deletion; or
- influence BioCortex runtime behavior.

The legacy `MutableSqliteV41` preflight remains byte-identical and continues to
return exactly eight gaps. Track B continues to carry
`CANDIDATE_EVIDENCE_SUBSTRATE_INTERFACE_UNREPRESENTED`; S3 only defines what a
future implementation must prove.

## Source-bound verification

After committing the seven S3 packet paths on top of
`a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259`, run:

```bash
./scripts/check-memory-temporal-evidence-adapter-s3.sh
```

The gate requires the S2 baseline as the direct parent, rejects replace refs,
grafts, shallow history, symlinks, hardlinks, mode drift, or any path outside
the seven-file allowlist. It archives committed `HEAD`, verifies every packet
and upstream source hash, runs the standard-library checker twice in a
sanitized environment, compares both byte streams with the fixed receipt, and
fences HEAD/index/worktree state.

No Cargo target is built: this packet explicitly permits no Rust delta. A PASS
proves only that the fail-closed S3 decision and S4 prerequisites are
source-bound and reproducible.
