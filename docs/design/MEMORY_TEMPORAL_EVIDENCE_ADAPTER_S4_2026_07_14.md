# Memory Temporal Evidence Adapter S4

Date: 2026-07-14

Status: **`SYNTHETIC_MECHANISM_IMPLEMENTED_BLOCKED_PRODUCTION`**

Decision: **`BLOCKED_FAIL_CLOSED` for real capture, production admission, and
BioCortex runtime influence**

## Outcome

S4 implements the five missing interface mechanisms preregistered by S3, but
only in a default-off synthetic lane:

1. a fresh physical SQLite read-only connection with `query_only`,
   `foreign_keys`, `is_readonly(main)`, and zero-`total_changes` checks;
2. one deferred transaction containing complete v43
   `load -> prepare -> project -> seal`;
3. an independent, content-free tombstone channel with terminal rejection for
   a tombstoned source that ever carried outgoing governance and pruning for an
   inbound tombstoned target;
4. complete-snapshot-derived relationship authority using the target's latest
   revision strictly before the source `recorded_at`, plus lossless
   `(source_key, provenance_sha256)` bindings; and
5. a field-private, non-Serde result that binds producer identity, snapshot
   payload SHA/bytes/counts/limits, request time, mapping version, prepared
   digest, projection digest, and pruning count.

The existing projector v0 and its adapter remain byte-identical. S4 is a
parallel store-owned v1 because `ab-store` cannot depend on `ab-bridge` without
creating a dependency cycle.

## Mechanical synthetic boundary

The store feature `temporal-evidence-s4-synthetic` is absent from default
features. The Bridge feature only forwards it. The store API consumes a permit
by value; permit fields are private, and the type implements neither `Clone`,
`Default`, nor Serde. Its sole safe constructor is `#[cfg(test)]` and
`pub(super)` inside the store module.

Consequently, enabling the feature can compile and review the API and Bridge
wrapper, but safe non-test code still cannot call it for any database path.
Store unit tests can exercise invented empty, non-empty, tombstoned, and
post-cutoff ledgers without creating a production read capability. An empty
ledger's canonical bytes and digest are verified as a determinism assertion,
not mislabeled as proof that the database originated from a particular
synthetic fixture.

The result's `synthetic_fixture_id=crate_unit_test_only_v0` is only a mechanism
marker carried by the unforgeable test permit. It is not capture provenance or
database-origin evidence.

The Bridge contains one `pub(crate)` forwarding wrapper. It has no CLI, MCP,
daemon, StateStore, Track B, or BioCortex runtime caller.

## Source-time authority rule

For every retained physical relationship, preparation searches the complete
validated ledger for:

```text
latest target revision where target.recorded_at < source.recorded_at
```

The comparison is strict. A target revision at the same second remains
ambiguous and is rejected by the v43 validator and again fail-closed by v1
preparation. The seven-field basis records source evidence/time and exact
target lineage/evidence/revision/time/tier.

Projection never re-compares the source tier to the cutoff-latest target tier.
This fixes the S3 P1 counterexample: a verified source may have legally related
to an observed target at time 100 even if the target later becomes
authoritative at time 200.

This is a **complete-snapshot-derived source-time basis**, not an original
physical-admission witness. Schema v43 has no immutable global append sequence
or persisted relationship witness. If physical insert-order audit is required,
a later schema must add it explicitly.

## Tombstone and cutoff rules

Tombstones are checked before mapping:

- `had_outgoing_governance=true` terminates the complete operation;
- otherwise every revision of the tombstoned lineage is absent from prepared
  evidence and projection; and
- retained relationships pointing to that lineage are pruned and counted.

All ordinary revisions, including those recorded after `knowledge_cutoff`,
remain bound into the snapshot and prepared digests. Projection alone selects
the latest per-lineage revision at or before the cutoff. Therefore an ordinary
post-cutoff revision may change counts, snapshot SHA, and prepared SHA, but it
cannot change claims, projected provenance, visible authority bases, or the
projection SHA. A known tombstone is the deliberate privacy exception.

## Projection semantics

The v1 projector keeps v0's deterministic semantics while using the source-time
authority basis:

- visible relationship graphs are topologically sorted;
- earliest suppression propagates through the DAG;
- a suppressed source may fire only an edge strictly earlier than its own
  suppression time; equal timestamps favor suppression;
- temporal selection order is
  `Current > Indeterminate > Future > Historical`;
- the highest tier inside that temporal class wins;
- multiple distinct values at the highest tier are `conflicted`; and
- load-bearing and agreeing evidence retain canonical source/provenance pairs.

The immutable views expose suppression kind, source evidence, effective time,
and validity/lifecycle boundaries for audit. They intentionally do not claim
that provenance for a historical authority-basis target is a currently selected
projection item; the lossless historical material remains inside the sealed
prepared digest.

## Read-only claim boundary

S4 promises a complete transactional SQLite snapshot. A read-only connection
may correctly observe a live WAL. It does **not** promise that an external
writer was globally paused. `immutable=1` is deliberately not used because it
can ignore a live WAL.

The returned object attests only this local mechanism. It does not prove data
ownership, capture authorization, policy-custodian appointment, source truth,
physical privacy deletion, or regulatory approval.

## Verification matrix

Seven S4 tests cover:

1. empty-ledger determinism and physical read-only/zero-write checks;
2. exact v43 identity rejection without read-path migration;
3. the later-target-upgrade source-time-authority counterexample;
4. post-cutoff data bound into the snapshot but excluded from projection;
5. inbound tombstone pruning and governed-source terminal rejection;
6. canonical required-claim ordering and missing-path non-creation; and
7. duplicate-claim and invalid-window rejection.

Fourteen existing S2 temporal-ledger tests run unchanged. Low-memory validation
uses one Cargo job, no incremental compilation, no default ONNX feature, one
test thread, and stripped debug information. Bridge is also compiled with only
the S4 forwarding feature.

These are correctness and boundary tests. S4 reports no latency, throughput,
memory-efficiency, model-quality, neuroscience, or BioCortex performance gain.

## Remaining blockers

S4 resolves the five S3 interface-mechanism gaps only in the synthetic lane.
The following remain independently blocked:

- `CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED`;
- `PRODUCTION_PRODUCER_PROFILE_UNADMITTED`;
- `CAPTURE_PROVENANCE_UNATTESTED`;
- `AUTHORITY_POLICY_CUSTODY_UNRESOLVED`;
- `PHYSICAL_PRIVACY_DELETION_UNRESOLVED`; and
- a cross-BioCortex transport using request-scoped opaque handles and a
  nonce/HMAC rather than raw ids, values, and source keys.

No legacy row is qualified and no Track B artifact binding is satisfied.
Side effects remain `NONE`.

## Next admissible step

S5 may preregister a production-profile and cross-repository interface review.
It must separately resolve capture/custody/deletion receipts, define opaque
transport handles, and bind a real candidate-evidence contract before any
runtime trial. S4 alone cannot unlock those steps.
