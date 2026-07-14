# BioCortex / Agent-Bridge Track B Evidence Substrate S2

Date: 2026-07-14

Status: **S2 source-bound verification packet; maximum outcome is
`READY_FOR_SEPARATE_S3_ADAPTER_REVIEW`; adapter and real capture remain
blocked**

## Outcome

The S1 temporal-evidence design now has an additive SQLite v43 mechanism: five
append-only truth ledgers, exact live schema and migration identity, an
internal synthetic-token writer, typed rejection codes, and an internal
complete canonical snapshot. The snapshot is full-ledger: its knowledge cutoff
is bound metadata and does not remove later-recorded rows.

This does not connect the substrate to `StateStore`, Bridge, MCP, the temporal
projector, or BioCortex. It does not qualify a legacy row, name a new producer
profile, authorize real/private capture, resolve physical deletion, or appoint
an authority-policy custodian. The admission decision remains
`BLOCKED_FAIL_CLOSED`.

## Bound implementation

- `crates/store/src/sqlite/temporal_evidence.rs`
  SHA-256: `1792da840e16de506049bffdca2c3e5fb498003aa811ec56d633fab651e35492`
- `crates/store/src/sqlite/temporal_evidence/tests.rs`
  SHA-256: `acba71edc6a8809d8761f13c802c4408a51ce211642b437037a35e56a12d6e61`
- `crates/store/src/sqlite.rs`
  SHA-256: `81d512cd8323d027aae898a846c2b5a4af53aa42ff7d31b9194ebfedc8a2e7d3`
- `crates/store/Cargo.toml`
  SHA-256: `cbc31c4c465267a39225f9dd520bcf00d64b7076f924f99643ffe81b44b6f062`
- `Cargo.lock`
  SHA-256: `4e2e14ff2806796690da12831c5f9a19a64497401b445b2e8501482ccb0ab4e1`

The reviewed live schema manifest SHA-256 is
`6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0`.
It includes all reserved-name objects and all non-autoindex objects attached to
the five truth tables, independent of object name or type. Names and attached
table names are normalized to lowercase because SQLite identifiers are
case-insensitive; runtime ledger SQL is independently `main.`-qualified. The
migration SHA-256 is
`f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb`;
it binds the migration manifest, schema digest, DDL encoding label, and full
DDL bytes.

The complete `truth_evidence.*` metadata namespace is reserved: migration from
v42 rejects any collision, while v43 verification requires exactly the three
reviewed identity rows and rejects unknown additions.

## Bound packet

- Design: `docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md`
  SHA-256: `dd837929fdd1acf29be4c17ce06f3dacd4ae25f2bb13cf6ed190b84f65098f5b`
- Contract:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json`
  SHA-256: `4dc7f459baa6de49755b79578c1ffdd6818c56d7f15916af72b024ef04c793da`
- Synthetic fixture:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_synthetic_v0.json`
  SHA-256: `28ed92bbf909a9ca24579966a54cee394545d798efd0fae0db8c572ddc5955da`
- Standard-library checker:
  `scripts/eval/check_memory_temporal_evidence_substrate_s2.py`
  SHA-256: `229afa062c1887c0b8337f14b679d70c86983af3261a8d1e7f45739adb8cee1b`
- Expected receipt:
  `scripts/eval/fixtures/memory_temporal_evidence_substrate_s2.expected.v0.tsv`
  SHA-256: `d139c6e6efbbbe2032b39478826cbc8b148691cf7f594314c30aeb15d7a363bf`
- Clean-HEAD gate: `scripts/check-memory-temporal-evidence-substrate-s2.sh`
  SHA-256: `169906cbe3104b6cf6fdbaa5de74bdaee434e6668efce502da70d0569880989d`

The clean gate emits the committed `HEAD`; this report intentionally does not
embed a self-referential commit or report digest.

## Evidence exercised

The `truth_evidence_s2_` Rust test family is the runtime evidence. Its filtered,
offline, single-job execution completed with 14 passed, 0 failed, and 445
filtered.

The complete low-memory `ab-store` library regression with default features
disabled also completed with 459 passed, 0 failed. This includes the historical
migration tests, which now verify that an empty v43 truth substrate is removed
atomically before replaying each older-version migration.

The prefixed cases cover:

- v42-to-v43 migration, empty truth ledgers, and no legacy-memory backfill;
- repeat-open identity and failure on metadata, object, persistent-view,
  non-reserved attached-trigger, lowercase or mixed-case temporary shadow, and
  temporary-object drift;
- atomic first-lineage/evidence admission, sequence allocation, canonical
  provenance, and deterministic full-ledger snapshot digest;
- exact latest-visible policy selection and rollback on a backdated policy that
  would invalidate admitted evidence;
- same-second target ambiguity, lower-tier suppression, cycles, durable
  relationship carry-forward, and rollback of a retroactively invalidating
  backdated target revision;
- inbound relationships to tombstoned targets, governance attestation, and the
  ban on later source revisions;
- raw update/delete rejection on every truth table;
- strict count/payload cap sentinels and verified read-only snapshots.
- iterative validation of a 9,999-lineage chain without call-stack recursion,
  plus bounded streaming rejection of control-character JSON expansion before
  the canonical payload reaches its byte sentinel.

The public fixture is invented mechanism data. It has two policies, three
lineages, four evidence revisions, two carried-forward relationships, and one
content-free tombstone. Evidence recorded at 180 and 350 remains in its
full-ledger snapshot despite cutoff 160. A legacy memory count of one remains
truth-row count zero after migration.

The packet checker additionally validates the fixed S2 boundary, recomputes
schema and migration digests from source, checks the exact table/index/trigger
shape, and rejects ten hostile fixture mutations. It pins all seven S1 packet
hashes and `crates/bridge/src/memory_truth_adapter.rs` at SHA-256
`c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023`.
That adapter still names `MutableSqliteV41` and its end-to-end test still
requires exactly eight gaps.

## Deterministic receipt

```text
schema	agent_bridge.memory_temporal_evidence_substrate_s2_receipt.v0
implementation_status	READY_FOR_SEPARATE_S3_ADAPTER_REVIEW
fixture_only	true
schema_version	43
ledger_format_version	0
tables	5
append_only_update_delete_triggers	10
schema_sha256	6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0
migration_sha256	f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb
schema_migration_present	true
schema_and_migration_identity_verified	true
crate_internal_synthetic_writer_present	true
crate_internal_full_ledger_snapshot_present	true
prefixed_rust_tests_at_least_6	true
synthetic_negative_cases_rejected	10
fixture_lineages	3
fixture_evidence_revisions	4
s1_packet_unchanged	true
mutable_profile	MutableSqliteV41
mutable_profile_gap_count	8
state_store_surface_present	false
bridge_surface_present	false
mcp_surface_present	false
store_adapter_present	false
producer_profile_changed	false
legacy_backfill	false
legacy_rows_qualified	false
real_capture_authorized	false
biocortex_runtime_influence	false
physical_privacy_deletion_resolved	false
authority_policy_custody_resolved	false
sentinels_cleared	true
decision	BLOCKED_FAIL_CLOSED
```

## Verification boundary

After commit, from a clean worktree:

```bash
./scripts/check-memory-temporal-evidence-substrate-s2.sh
```

The gate accepts only the twelve reviewed S2 paths relative to integration
commit `1c1770579c46f325ef4a1dee3f870bfe20a5a09a`, which already contains S1 and
the separately merged Track B artifact-dependency graph. It materializes the
complete source from `git archive HEAD`, verifies this report's artifact
hashes, runs the checker twice in a sanitized environment, compares both byte
streams to the fixed receipt, and then runs:

```text
cargo test --offline --locked -j 1 -p ab-store --lib \
  --no-default-features truth_evidence_s2_ -- --test-threads=1
```

The build uses one job, disabled incremental compilation, the offline cache,
and an isolated target directory. The gate fences committed `HEAD`, index, and
worktree state across the run.

## Admission decision

`READY_FOR_SEPARATE_S3_ADAPTER_REVIEW` means only that the independently
identified S2 storage mechanism is ready to be reviewed by the next layer. S3
must still design a producer profile and mapping, prove that read-only identity
is bound at the adapter boundary, decide custody and privacy deletion, and keep
all incomplete cases fail-closed. No S2 result is a BioCortex performance or
scientific result.
