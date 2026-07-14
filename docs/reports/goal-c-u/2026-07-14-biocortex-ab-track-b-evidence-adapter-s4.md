# BioCortex / Agent-Bridge Track B Evidence Adapter S4

Date: 2026-07-14

Status: **synthetic mechanism implemented; production remains fail-closed**

Decision: **`BLOCKED_FAIL_CLOSED`**

## Result

The S3 interface contract is now implemented as a parallel temporal truth
projection v1 inside `ab-store`. A fresh physical read-only SQLite connection
performs complete v43 load, tombstone-aware preparation, source-time authority
mapping, deterministic projection, and sealing in one deferred transaction.
The full ledger never crosses into Bridge.

The implementation passes the S3 P1 counterexample: a relationship admitted
against an observed target revision strictly before the source time remains
valid after a later authoritative target upgrade. It also preserves each
source key with its provenance digest, retains ordinary post-cutoff revisions
in the snapshot/prepared binding without leaking them into the projection, and
distinguishes prunable inbound tombstones from terminal governed-source
tombstones.

This does not deploy a production adapter. The feature is default-off and the
permit has no safe non-test constructor. Bridge has one crate-private wrapper
and no runtime caller. Existing truth projector v0,
legacy memory adapter, MCP, daemon, Track B graph, and BioCortex behavior remain
unchanged.

## Validation completed

- S4 filtered tests: `7 passed, 0 failed`.
- Existing S2 temporal-evidence regression tests: `14 passed, 0 failed`.
- `ab-store` feature build: passed with default features disabled.
- `ab-bridge` forwarding-feature build: passed with default features disabled.
- Physical boundary exercised: read-only open, `query_only=1`,
  `is_readonly(main)=true`, `total_changes=0`, missing path not created.
- Canonical boundary exercised: repeated empty projection and reordered
  required claims produce identical prepared/projection digests.

Commands use `CARGO_BUILD_JOBS=1`, `CARGO_INCREMENTAL=0`, `-j1`, one test
thread, offline dependencies, and `-C debuginfo=0` to stay within the host's
memory limit after the earlier OOM.

## Claims deliberately not made

S4 does not provide performance numbers because this tranche is a correctness
and interface-boundary experiment, not a benchmark. It does not show BioCortex
quality improvement, model training benefit, neuroscience validity, legal or
institutional approval, capture authorization, policy custody, source truth,
or physical deletion.

The source-time relationship basis is reconstructed from the complete
validated snapshot. It is not the original physical-admission witness. The
read-only attestation covers one SQLite transaction, including a live WAL when
present; it does not prove global writer quiescence.

## Remaining state

Five S3 operational/admission gaps remain, plus the cross-BioCortex opaque
transport contract:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED
CAPTURE_PROVENANCE_UNATTESTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
```

Accordingly:

```text
real_capture_authorized=false
production_profile_active=false
legacy_rows_qualified=false
track_b_artifact_binding_satisfied=false
mcp_surface_present=false
biocortex_runtime_influence=false
side_effects_unlocked=NONE
decision=BLOCKED_FAIL_CLOSED
```

## Bound S4 sources

The clean-HEAD gate verifies these path-to-SHA bindings from `git archive
HEAD`; this report deliberately does not bind its own digest:

- `crates/bridge/Cargo.toml`: `b2aec2f09b2055f2fb8045c45ac324570507df02e27e43a432860adecbc043e1`
- `crates/bridge/src/lib.rs`: `69bb47ea3eeb47fc54a7997e52a2f529e2c16818a3b75f6bfa1db34ae7a3a8c5`
- `crates/bridge/src/memory_temporal_evidence_adapter_v1.rs`: `e706f8836cb54751f07beac551dd5a3090e7274b55b7fb64372507df33320668`
- `crates/store/Cargo.toml`: `46ee1949da92d72d3ca071fdb8e9fe42d2b313504e6a7f8e938ce419ef7cfa2c`
- `crates/store/src/lib.rs`: `f9af5021c15327c38b6d0516441171bee4dbd92f2ee0410f9f0af3122b864119`
- `crates/store/src/sqlite.rs`: `34163933bb1df3d80eb0f0b88c49ce895b6157f8bab2d1232b12607263e623b8`
- `crates/store/src/sqlite/temporal_evidence.rs`: `f03a80f45c5c9e472ee68d05f10609c8edcd24ace3f1a5b2e521c68bf86a7299`
- `crates/store/src/sqlite/temporal_evidence/projection_v1.rs`: `24c086ae8c567ea629a13ec1291e1933ef1d615ac002b6b74f0ec82741af3388`
- `crates/store/src/sqlite/temporal_evidence/tests.rs`: `24254bfa4f473ab49cad90c251519212d3e88c84ece73df008a51d5b099af711`
- `docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S4_2026_07_14.md`: `9137c77cd3295edca89d8647088527463e629a622208ebcd90dbd669aff1f02a`
- `scripts/check-memory-temporal-evidence-adapter-s4.sh`: `d151dd5fe26a5644d371a25b2a0a265deddb26b505230a159180c8848acdfed8`
- `scripts/eval/check_memory_temporal_evidence_adapter_s4.py`: `ef766f25056e580a1b27e1dbd9842aba15146d23b8be349467f88649ba2e3ad9`
- `scripts/eval/fixtures/memory_temporal_evidence_adapter_s4.expected.v1.tsv`: `4524938ad3dcc2a63f59db37f0cfab8fc3fb7cbf7d4840586e1bbae344dc52fd`

## Next step

After the clean-HEAD S4 gate passes, this tranche may be committed, fast-forward
merged, and pushed. The next research tranche is S5: a fail-closed production
profile and opaque cross-repository interface preregistration, not runtime
activation.
