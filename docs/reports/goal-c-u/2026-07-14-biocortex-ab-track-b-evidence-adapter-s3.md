# BioCortex / Agent-Bridge Track B Evidence Adapter S3

Date: 2026-07-14

Status: **source-bound fail-closed preregistration; maximum outcome is
`PREREGISTERED_BLOCKED_PENDING_S4_INTERFACE`**

Decision: **`BLOCKED_FAIL_CLOSED`**

## Outcome

The S3 adapter review is complete, and a direct adapter was deliberately not
implemented. The v43 temporal-evidence substrate and truth projector v0 have
one P1 semantic incompatibility:

- S2 evaluates relationship authority at source knowledge time using the
  strict-before target revision, while projector v0 recomputes authority from
  the cutoff-latest target revision.

Four additional interface gaps prevent a trustworthy boundary. Projector v0
has no independent channel for the S2 tombstone attestation and would need to
re-carry retained, logically deleted revision content; it drops S2 provenance
digests; the internal snapshot does not yet carry an unforgeable cross-crate
read-only-open attestation; and a projection cannot be sealed to its complete
source snapshot. Five operational/admission gaps keep production data and
Track B runtime use independently blocked.

S3 therefore contributes only a design, contract, invented fixture,
standard-library checker, fixed receipt, clean-HEAD gate, and this report. It
adds no Rust or Cargo delta, reserves no producer profile, calls no projector,
and changes no StateStore, Bridge, MCP, Track B binding, or BioCortex runtime.

## Bound S3 packet

- Design:
  `docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S3_2026_07_14.md`
  SHA-256: `b2b236a32300a10ceb77a35ddb5b9217d390db5ddb1d26d73b3bf4fce8bd1fb0`
- Contract:
  `scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json`
  SHA-256: `0efefdc38111bac5f344335be425dc6cf931fa509284833b959e326f7d2e8c2a`
- Synthetic fixture:
  `scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_synthetic_v0.json`
  SHA-256: `ce2facc5989883eafb95b7e184868792dfdf511a6bc06c739d01f3556178afea`
- Standard-library checker:
  `scripts/eval/check_memory_temporal_evidence_adapter_s3.py`
  SHA-256: `1cbc58593e636f57e9f6e35b63ba7cc85875c02b51cd90b5ffda09af5d55e4dd`
- Expected receipt:
  `scripts/eval/fixtures/memory_temporal_evidence_adapter_s3.expected.v0.tsv`
  SHA-256: `1d8eaa508bf4b53550c2dc9bed573c989edbefbcc550e7604ecfafdb7df4ad03`
- Clean-HEAD gate:
  `scripts/check-memory-temporal-evidence-adapter-s3.sh`
  SHA-256: `6b141ebaf34452a572c5ebc179e8c707c4a840fac2866c898a59499a0c6dbcb0`

This report intentionally does not embed its own digest or the future commit
id. The clean gate emits both from committed `HEAD`.

## Bound upstream S2 mechanism

The S2 commit is
`a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259`. Schema v43 has reviewed schema
SHA-256 `6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0`
and migration SHA-256
`f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb`.
The complete twelve-file S2 tranche is pinned:

- `Cargo.lock`:
  `4e2e14ff2806796690da12831c5f9a19a64497401b445b2e8501482ccb0ab4e1`
- `crates/store/Cargo.toml`:
  `cbc31c4c465267a39225f9dd520bcf00d64b7076f924f99643ffe81b44b6f062`
- `crates/store/src/sqlite.rs`:
  `81d512cd8323d027aae898a846c2b5a4af53aa42ff7d31b9194ebfedc8a2e7d3`
- `crates/store/src/sqlite/temporal_evidence.rs`:
  `1792da840e16de506049bffdca2c3e5fb498003aa811ec56d633fab651e35492`
- `crates/store/src/sqlite/temporal_evidence/tests.rs`:
  `acba71edc6a8809d8761f13c802c4408a51ce211642b437037a35e56a12d6e61`
- S2 design:
  `dd837929fdd1acf29be4c17ce06f3dacd4ae25f2bb13cf6ed190b84f65098f5b`
- S2 report:
  `974d45a40b66517ce2c4445731c76f8dc0af66f976fa634cbf024ab7b020a337`
- S2 clean gate:
  `169906cbe3104b6cf6fdbaa5de74bdaee434e6668efce502da70d0569880989d`
- S2 checker:
  `229afa062c1887c0b8337f14b679d70c86983af3261a8d1e7f45739adb8cee1b`
- S2 expected receipt:
  `d139c6e6efbbbe2032b39478826cbc8b148691cf7f594314c30aeb15d7a363bf`
- S2 contract:
  `4dc7f459baa6de49755b79578c1ffdd6818c56d7f15916af72b024ef04c793da`
- S2 synthetic fixture:
  `28ed92bbf909a9ca24579966a54cee394545d798efd0fae0db8c572ddc5955da`

The checker additionally pins `crates/bridge/src/memory_truth.rs` at
`2e46a521332820b07171b425c95004f35a98887c7c49a2d78baf7740f07195a4`
and `crates/bridge/src/memory_truth_adapter.rs` at
`c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023`.
The latter still recognizes only `MutableSqliteV41`, invokes no projector, and
its end-to-end test still asserts exactly eight gaps.

## Bound Track B planning state

S3 does not satisfy or rewrite an existing Track B artifact binding. It pins
the current dependency-graph packet:

- graph report:
  `99092b968afe09bf96849c64558b8fce3785787b502493428dcb2e8366585395`
- graph gate:
  `20e0b36d583ad729b992a423834dbb7c05245c3689a5887e53fb04103222b001`
- graph checker:
  `cd92c7c309b4cee07f16256a59b33abb3da4b526c825780e7a3e92ab30d53b26`
- graph expected receipt:
  `8c0025b8e7e905b130ffde3e3c9a070ef2f0198941a84193b938e541f426f088`
- graph fixture:
  `8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af`

The graph fixture still contains
`CANDIDATE_EVIDENCE_SUBSTRATE_INTERFACE_UNREPRESENTED`. S3 records the future
interface contract but leaves its status
`PREREGISTERED_NOT_IMPLEMENTED_OR_BOUND`, its binding false, and all side
effects locked.

## Frozen gaps and counterexamples

The exact ten-code set is:

1. `AUTHORITY_POLICY_CUSTODY_UNRESOLVED`
2. `CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED`
3. `CAPTURE_PROVENANCE_UNATTESTED`
4. `CONTENT_FREE_TOMBSTONE_CHANNEL_UNREPRESENTED`
5. `PHYSICAL_PRIVACY_DELETION_UNRESOLVED`
6. `PRODUCTION_PRODUCER_PROFILE_UNADMITTED`
7. `PROVENANCE_DIGEST_CHANNEL_UNREPRESENTED`
8. `READ_ONLY_OPEN_IDENTITY_UNBOUND`
9. `RELATIONSHIP_SOURCE_TIME_AUTHORITY_BASIS_UNREPRESENTED`
10. `SEALED_SNAPSHOT_PROJECTION_BINDING_UNREPRESENTED`

The six invented cases distinguish schema identity from data authority; an
inbound tombstoned target from a tombstoned governance source; strict-before
source-time authority from cutoff-latest authority; a complete full ledger from an adapter
prefilter; and per-evidence provenance from projection-to-snapshot sealing.
Both tombstones use the actual S2 `content_free_governance_v0` attestation
format and a digest derived from its canonical payload.

The source-time target basis is derived from the complete validated ledger.
S3 does not claim that v43 persisted the exact target revision used at the
original physical insert; it did not. If physical admission-order audit becomes
a requirement, a later schema must add an immutable witness or global sequence.
The checker rejects 28 adversarial changes, including fake receipts, invented
capabilities, placeholder tombstones, governed-source release, cutoff
prefiltering, profile promotion, runtime activation, unknown fields, and
duplicate JSON keys.

## Deterministic receipt

```text
schema	agent_bridge.memory_temporal_evidence_adapter_s3_receipt.v0
design_status	PREREGISTERED_BLOCKED_PENDING_S4_INTERFACE
fixture_only	true
baseline_commit	a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259
s2_schema_version	43
s2_ledger_format_version	0
s2_schema_sha256	6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0
s2_migration_sha256	f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb
s2_packet_unchanged	true
current_projector_schema	agent_bridge.truth_projection.v0
direct_projector_v0_mapping_allowed	false
current_mutable_profile	MutableSqliteV41
current_mutable_profile_gap_count	8
s3_gap_count	10
synthetic_case_count	6
synthetic_negative_cases_rejected	28
content_free_tombstone_channel_required	true
placeholder_tombstone_evidence_allowed	false
governed_tombstone_source_terminal	true
inbound_tombstoned_target_prunable	true
relationship_authority_basis	complete_snapshot_latest_target_strictly_before_source_recorded_at
cutoff_latest_tier_recheck_allowed	false
provenance_digest_preservation_required	true
read_only_identity_attestation_required	true
sealed_snapshot_projection_binding_required	true
schema_identity_proves_capture_authority	false
producer_profile_reserved	false
s3_adapter_present	false
projector_invoked	false
legacy_rows_qualified	false
real_capture_authorized	false
physical_privacy_deletion_resolved	false
authority_policy_custody_resolved	false
track_b_candidate_interface_status	PREREGISTERED_NOT_IMPLEMENTED_OR_BOUND
track_b_artifact_binding_satisfied	false
state_store_surface_present	false
bridge_runtime_surface_present	false
mcp_surface_present	false
biocortex_runtime_influence	false
side_effects_unlocked	NONE
sentinels_cleared	true
decision	BLOCKED_FAIL_CLOSED
```

## Verification boundary

After commit, from a clean worktree, run:

```bash
./scripts/check-memory-temporal-evidence-adapter-s3.sh
```

The gate requires a single S3 commit whose direct parent is
`a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259` and whose delta is exactly the
seven packet files. It rejects replace refs, grafts, shallow history, symlinks,
hardlinks, and mode drift; materializes committed `HEAD` with `git archive`;
verifies the packet and all 19 upstream source hashes; runs the checker twice
under a sanitized environment; compares both byte streams to the fixed TSV;
and fences HEAD, index, and worktree state.

No Cargo command is run because a Rust or manifest delta is forbidden. The
validation is intentionally low-memory and standard-library-only.

## Next admissible step

S4 may implement a parallel projection v1 only after a fresh review of the
contract in the design document: independent tombstones, a full-ledger-derived
source-time relationship basis, lossless provenance, an unforgeable read-only v43
snapshot, and atomic map-plus-project output sealed to the full snapshot.

That future implementation still may not authorize real/private capture,
production profile admission, authority-policy custody, physical deletion, or
BioCortex runtime use. Those require separate receipts and gates; none can be
inferred from a successful S3 check.
