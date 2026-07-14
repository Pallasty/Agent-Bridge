# BioCortex / Agent-Bridge Track B Candidate Binding S5

Date: 2026-07-14

Status: **synthetic candidate interface implemented; schema-compatible but not
live-bound**

Decision: **`BLOCKED_FAIL_CLOSED`**

## Result

S5 adds a default-off, synthetic-only source interface from an exact sealed S4
request/projection pair to request-scoped Track B-compatible opaque handles.
The pair is created only by the same call that invokes S4; its private fields
prevent a later request from being retrofitted onto an older projection. The
interface consumes that non-cloneable pair and permit, then drops all raw S4
material before returning a field-private, non-serializable result.

It defends the S4 projection boundary rather than treating `required_claims` as
an export filter: the non-empty requested claim set must exactly equal the
complete projected claim set. The permit also freezes the complete S4
snapshot/prepared/projection tuple, so a matching visible projection digest
cannot hide a different underlying snapshot.

Handle derivation uses candidate-role-separated `ring` HMAC-SHA-256 domains,
request nonce and TTL, strict length framing, collision termination, and only
opaque `prj_`, `clm_`, `ref_`, `prd_`, `val_`, `evd_`, and `src_` outputs. The
transport key id is included in the authenticated-message framing. Top evidence
is represented by handles, not just a count.

This does not deploy a producer or transport. The sole safe permit constructor
exists only in store tests. Bridge has one crate-private forwarding wrapper and
no runtime caller. No candidate builder, final context builder, truth manifest,
MCP, StateStore, daemon, cross-repository path, or BioCortex behavior is
connected.

## Validation completed

- S5 filtered tests: `7 passed, 0 failed`.
- Existing S4 regression tests: `7 passed, 0 failed`.
- Existing S2 temporal-evidence regression tests: `14 passed, 0 failed`.
- `ab-store` S5 feature build: passed with default features disabled.
- `ab-bridge` S5 forwarding-feature build: passed with default features
  disabled.
- Default-off `ab-store` and `ab-bridge` builds: passed.
- Candidate schema is canonical, closed, and bound at
  `edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77`.
- Frozen S4 projection/wrapper/SQLite files remain byte-identical.

Commands use `CARGO_BUILD_JOBS=1`, `CARGO_INCREMENTAL=0`, `-j1`, one test
thread, offline locked dependencies, disabled default ONNX features, and
`-C debuginfo=0` to control memory use after the earlier OOM.

## Claims deliberately not made

The foundational schema-pack manifest binds the existing four-schema Track B
pack. It does not bind the S5 Rust source or candidate schema. S5 demonstrates
source-schema compatibility; it does not satisfy complete source-artifact,
trial-artifact, truth-manifest, or live Track B binding.

The request nonce is not backed by a durable cross-process single-use registry.
The strict claim-set rule is suitable for isolated synthetic snapshots but is
not a production multi-claim export mechanism. The HMAC object is not exposed
as a network or filesystem serializer.

S5 provides no performance numbers because this tranche tests correctness and
interface boundaries, not performance. It does not establish BioCortex quality
improvement, fermionic-algorithm benefit, model training benefit, neuroscience
validity, capture authorization, policy custody, source truth, privacy
deletion, legal approval, or institutional recognition.

## Remaining state

The synthetic candidate-interface mechanism is implemented. These five gaps
remain:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

Accordingly:

```text
source_artifact_compatibility_binding=true
source_artifact_binding_satisfied=false
track_b_artifact_binding_satisfied=false
track_b_live_binding_satisfied=false
candidate_context_builder_bound=false
truth_manifest_binding_satisfied=false
nonce_single_use_registry_implemented=false
real_capture_authorized=false
production_profile_active=false
legacy_live_binding_satisfied_count=0
trial_live_binding_satisfied_count=0
mcp_surface_present=false
state_store_surface_present=false
biocortex_runtime_influence=false
side_effects_unlocked=NONE
decision=BLOCKED_FAIL_CLOSED
```

## Bound S5 sources

The clean-HEAD gate verifies the final path-to-SHA bindings from `git archive
HEAD`. This report deliberately does not bind its own digest. The bindings are
filled only after every other S5 source is frozen.

- `Cargo.lock`: `f169c36a6bb46ff5e550dcc71d058e80033bd23fb0a938aea5d2ec9e4ee9ad2b`
- `crates/bridge/Cargo.toml`: `f104b2885a8811d7e7c62a6f4c44fc6b29f10df877477c88d0b0d7551468ee2a`
- `crates/bridge/src/lib.rs`: `31627925116e72b78f0584a370c8a5f0e6aaafa6e0afd8f948fe8d7f0c1fade5`
- `crates/bridge/src/memory_track_b_candidate_evidence_v1.rs`: `4d66cbb3536691143f04260594263ce44a059b2b7d49bb7934cc9666769568e4`
- `crates/store/Cargo.toml`: `35047815966fb27e78f46c57b5bb45be62477488049e3b60a6365955330fdcb9`
- `crates/store/src/lib.rs`: `1a11af7df3b78c6823165a9cde55822b40ee8708f257aa661b7dd423fd8feb97`
- `crates/store/src/sqlite/temporal_evidence/tests.rs`: `29f091badbfba4fa244e13356174f69d71b8370cf4523dbd84b8858ff00dedf2`
- `crates/store/src/temporal_candidate_evidence.rs`: `5ae6638e05f32dbe9314815a1caddd33620a4ed950fea2aee6f442a27809e9aa`
- `docs/design/MEMORY_TEMPORAL_CANDIDATE_BINDING_S5_2026_07_14.md`: `5dc2277dc79a3ce8a00c61dc5c0d2341d40533f6cf3c7bfa3ee426a8fb7fecb4`
- `docs/design/fixtures/biocortex-ab-track-b-candidate-evidence-envelope-schema-v0.json`: `edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77`
- `scripts/check-memory-temporal-candidate-binding-s5.sh`: `b764baa2d30c48a90cd459fc0a7a506c3f1eab0571d43c72084a27b9d908e56b`
- `scripts/eval/check_memory_temporal_candidate_binding_s5.py`: `15750ce6a888a1db4513687af89794fdcbe6131c3cef68c8771d43c601b5200e`
- `scripts/eval/fixtures/memory_temporal_candidate_binding_s5.expected.v0.tsv`: `6e31091eddf1e468520440c55ecd781a3c9ab19c9e973a52f06ef510a62a4d72`

## Next step

After the clean-HEAD S5 gate passes, this tranche may be committed,
fast-forward merged, and pushed. S6 may preregister—but must not activate—a
complete S5 source manifest and replay-safe cross-repository transport plus
candidate-context artifact closure. Production remains independently blocked
on authority/custody, capture provenance, physical deletion, and producer
admission.
