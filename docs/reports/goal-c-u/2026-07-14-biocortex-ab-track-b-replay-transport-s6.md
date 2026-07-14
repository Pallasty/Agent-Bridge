# BioCortex AB Track B replay transport S6

Date: 2026-07-14

Status:
`SYNTHETIC_DETACHED_VERIFIER_CONTRACT_IMPLEMENTED_NOT_TRANSPORT_NOT_DURABLE`

Decision: `BLOCKED_FAIL_CLOSED`

## Result

S6 completed the bounded preregistration step. It froze the full historical S5
feature delta, resolved the S5 payload/logical-envelope ambiguity with an
explicit detached exact-payload profile, authenticated a deterministic
split-wire vector, and implemented a store-local executable specification for
exact-byte S5 verification and atomic process-local replay consumption.

It did not deploy or enable a transport. There is no S6 Bridge feature or
wrapper, runtime caller, StateStore/SQLite implementation, filesystem/network
path, MCP/CLI/daemon surface, exporter, BioCortex consumer, or candidate-context
builder. The authenticated inner payload still sets transport authorization,
live binding, and BioCortex influence to false and side effects to `NONE`.

## Source closure

The canonical S5 source manifest is bound to:

```text
source_commit  8739b69fb59fd704dacfe1a44bfc411ed9ebb913
parent_commit  486f04fb9a967a9a6cf5272f82f36cc0d7e787ad
source_tree    d4ba782665fac2c55af60e1c0a988a327b3535dd
scope          exact_s5_feature_commit_14_path_delta
artifact_count 14
manifest_sha   309f2533ef7b78d0c1f252325c0f79ab1300f8f68837a5a75ce7c14d8b011d6a
```

The checker independently derived the Git diff, parent, tree, paths, modes,
byte counts, SHA-256 values, and blob OIDs from the historical commit. The
manifest includes all 14 paths, including the S5 report and the executable mode
of the S5 gate.

This is historical source identity only. It is not a build attestation, current
binary provenance, remote producer identity, or key-custody attestation.

## Exact-byte vector

The deterministic synthetic vector verified:

```text
exact_payload_bytes             2182
exact_payload_sha256            41bd94a261fb053a8d3aca7c6776f2e719986626eb2d9f8915d93bdf6f928a40
authenticated_route_sha256      4daf7e24e35e79957aff9cdc5eaa182c2cf87169b56872aee8eaef9ef3d7d5b2
s5_exact_payload_hmac_sha256    871a7cf089767123f26ede2c58ecf86fd5defb1638ea2b09b1761eaa563f50f0
s6_route_payload_hmac_sha256    84c6aedbe93a93c215b07290a1af1a9b11051a93c4a3ce10ef46250434c55e8a
replay_identity_sha256          7c21a79214624b4c1c259d38aeff4b228d4df0071d180be249b78a5c47e1e8a5
scope_commitment_sha256         aef78050b26a59db80a6ba45b4c2c1aebe663e26fbc52dae228482950626fb27
```

The standard-library checker authenticated the exact decoded payload before
strict parsing, recomputed both HMAC layers, verified the synthetic S5
request-scoped handles and claim-binding HMAC, required canonical padded base64,
joined every inner/outer trial identity, rejected 47 source, byte,
authentication, identity, time, boundary, and replay mutations, and admitted
exactly one first atomic replay consumption.

The Rust module separately verified caller-owned exact bytes with the S5 ring
HMAC before parse, rejected duplicate/unknown/noncanonical JSON, enforced the
closed S5 schema and boundary, joined a test-only permit identity, and made one
sealed `consume_once` call as the last fallible operation. The private result
retains the exact bytes without a getter, Clone, Serde, or public export.

Replay uniqueness is `(s5_transport_key_id, request_nonce)`. A different trial
cannot make a nonce reusable. The scope commitment additionally binds source
manifest, payload profile, handle-key identity, trial/contract/case/request,
projection handle, time window, and payload digest. The only registry is a
mutex-protected test implementation and explicitly reports `durable=false`.

## Verification

Low-memory validation used one Cargo job, disabled incremental compilation,
stripped debug information, disabled default ONNX features, locked offline
dependencies, and one test thread.

Results:

- S6 exact-byte/replay tests: 7 passed, 0 failed;
- S5 candidate-binding regressions: 7 passed, 0 failed;
- S4 projection regressions: 7 passed, 0 failed;
- S2 temporal-ledger regressions: 14 passed, 0 failed;
- S6 store feature check: passed;
- default-off store check: passed;
- Bridge with the existing S5 feature only: passed;
- default-off Bridge check: passed;
- S6 structural/purpose checker: passed with 47 mutation rejections and one
  first-consume success;
- S5 purpose checker: unchanged and passed;
- `git diff --check`: passed.

Existing workspace warnings about a Greek test identifier, an unused vector
helper, and pre-existing Bridge dead/private-interface items remained unchanged.
No new S6 warning was reported.

These checks establish correctness and boundary behavior only. They establish
no latency, throughput, memory-efficiency, model-quality, BioCortex,
neuroscience, or fermionic-algorithm performance gain.

## Track B boundary

S6 pins the identity-composition manifest, truth-manifest schema, review schema,
candidate schema, foundational manifest, and truth-referent schema. This is
source compatibility, not live binding. S5 still lacks `ast_` assertion handles,
authority/currentness basis digests, gold evidence and private-map custody
receipts, selected-case producer identity, and expected response mode. No truth
manifest, candidate context, final context, review readiness, live ledger, or
real run is claimed.

## Remaining blockers

The original five blockers remain exactly unchanged:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

Durable restart/crash-safe replay, authorized successor payload semantics,
build/producer identity, key custody, and context construction also remain
absent. S6 closes only the historical source-manifest and transport-contract
preregistration gaps; it closes no live transport or production blocker.

## Artifact digests

- `crates/store/Cargo.toml`: `7450956bd3e2e119e386de687f5f4d0ed6cebfb689bc84626473b6e11b14326f`
- `crates/store/src/lib.rs`: `4e357d77d35d82c7fe6ac8de5b1870af7296cf10c72cf57ff684e49625a0638b`
- `crates/store/src/temporal_replay_transport.rs`: `f35777474a87a475a9cae3411c697974691e33ddbf94f9379b790a970ba7e4d6`
- `docs/design/MEMORY_TEMPORAL_REPLAY_TRANSPORT_S6_2026_07_14.md`: `76b01248c0d54eafbafc733d26ef2889092e8c4c1bd135eddbe1575eb30cf78c`
- `docs/design/fixtures/biocortex-ab-track-b-candidate-exact-payload-profile-v0.json`: `fe3b66ad1d5711f38e790cf792a0db63bd7879ce9795c07f745ab9127575be23`
- `docs/design/fixtures/biocortex-ab-track-b-replay-transport-contract-v0.json`: `4b54057fe78fd5eb760c89b86e3018003e4cf0a1b354ca720007927e7b005e74`
- `scripts/check-memory-temporal-replay-transport-s6.sh`: `b401b5a88fae3d71aa427d7b2704ae0d3a4a3288ece15c6007a76d2be0cf4733`
- `scripts/eval/check_memory_temporal_replay_transport_s6.py`: `9505ba2a20abd66c499df8d20884da67ca00f95bfeb9742c0c3d91e2e0b53b93`
- `scripts/eval/fixtures/memory_temporal_replay_transport_s6.expected.v0.tsv`: `4018412b2e87d20bc728efc91626579884c1bbf72579169e526911d6f3c87430`
- `scripts/eval/fixtures/memory_temporal_replay_transport_s6_s5_source_manifest_v0.json`: `309f2533ef7b78d0c1f252325c0f79ab1300f8f68837a5a75ce7c14d8b011d6a`
- `scripts/eval/fixtures/memory_temporal_replay_transport_s6_synthetic_v0.json`: `8850862deafefac5c86099116d7da4307af5b844a732ad72246d8f953c56dc1f`

## Next step

After independent review and the committed clean-HEAD S6 gate pass, this tranche
may be merged and pushed. The next research tranche should first define an
authorized successor payload and authority/custody decision, then implement a
durable content-free replay tombstone with restart, crash, concurrent-process,
and indeterminate-commit tests. A Bridge shadow caller is not yet admissible.
