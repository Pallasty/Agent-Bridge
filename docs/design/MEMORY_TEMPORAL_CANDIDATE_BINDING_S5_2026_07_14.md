# Memory Temporal Candidate Binding S5

Date: 2026-07-14

Status: **`SYNTHETIC_CANDIDATE_INTERFACE_IMPLEMENTED_SCHEMA_COMPATIBLE_NOT_LIVE`**

Decision: **`BLOCKED_FAIL_CLOSED` for cross-repository transport, real capture,
production admission, Track B trial use, and BioCortex runtime influence**

## Outcome

S5 implements one missing S4 mechanism: a source-level candidate-evidence
interface from an exact sealed S4 projection to the shape required by the
existing BioCortex / Agent-Bridge Track B truth-referent contract. It is a
default-off, synthetic-only interface. It is not a deployed producer, a
serializer, a transport, a candidate-context builder, or a live Track B
artifact binding.

The interface consumes these values together:

1. a field-private, one-shot synthetic permit;
2. an inseparable, field-private request/projection pair created by one S4
   projection call; and
3. the bind-time evaluation timestamp.

The pair is not reconstructed after projection. Its sole safe constructor owns
the request, passes a clone into S4, and retains the returned sealed projection
with that same request. The pair implements neither Clone nor Serde and is
consumed by binding. This prevents a later request with a coincidentally equal
visible claim set from being retrofitted onto an older projection.

The returned object contains request-scoped opaque handles and derived state
only. It does not retain the S4 projection, raw referent or predicate ids, raw
values, raw evidence ids, source keys, provenance digests, or secret key
material. The object is field-private, non-Serde, non-cloneable, and has no
transport method.

## Exact-claim fail-closed rule

S4's `required_claims` is not an output filter: the projection contains the
union of requested claims and all claims visible in the snapshot. S5 therefore
does not assume that supplying an allowlist makes a projection safe to export.

S5 requires a non-empty request and checks that the complete projected claim
pair set is exactly equal to the request pair set. Any missing claim, ambient
claim, duplicate projected pair, or request/projection mix terminates the whole
operation. S5 never silently filters a wider projection.

This rule makes the source interface safe for isolated synthetic snapshots. It
is deliberately restrictive and remains a production blocker for ordinary
multi-claim databases.

## Complete source tuple binding

The permit accepts only the inseparable pair and freezes its original request
digest and complete S4 projection identity tuple, including:

- S4 schema, mode, producer profile, mapping version, and synthetic marker;
- exact SQLite v43 schema and migration digests;
- schema meta version, ledger format, and canonical order;
- request times and all projection limits;
- snapshot payload digest, byte count, table counts, and table limits;
- prepared-input digest, projection digest, and pruned-relationship count; and
- read-only, query-only, and zero-total-changes attestations.

Binding re-derives and compares that complete tuple. A matching projection
digest alone is insufficient: a post-cutoff snapshot/prepared-input change is
rejected even when the visible projection digest remains identical.

## Track B identity compatibility

The candidate envelope schema is closed Draft 2020-12 JSON Schema and canonical
sorted pretty JSON at rest. It reuses the foundational Track B identity spine:

- `trial_id` and other labels are lowercase bounded labels;
- `case_id` is exactly `case_` plus 32 lowercase hexadecimal characters;
- claim, referent, and predicate handles are exactly
  `clm_`, `ref_`, and `prd_` plus 32 lowercase hexadecimal characters; and
- the foundational truth-referent schema digest and foundational schema-pack
  manifest digest are named explicitly.

The new schema digest is
`edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77`.
The foundational schema-pack manifest does not bind the S5 Rust implementation
or the new schema. S5 therefore records schema compatibility only:

```text
source_artifact_compatibility_binding=true
source_artifact_binding_satisfied=false
track_b_artifact_binding_satisfied=false
track_b_live_binding_satisfied=false
```

The clean-HEAD gate freezes the S5 source delta for review, but it is not a
trial artifact manifest and cannot be substituted for one.

## Opaque handle construction

Every handle is derived with `ring` HMAC-SHA-256. Domains are separated for the
candidate-evidence role and for projection, claim, referent, predicate, value,
evidence, source, and claim-binding purposes. Each input part is length-framed
with an unsigned 64-bit big-endian byte length.

The handle scope binds trial, contract, case, request, a non-zero 256-bit
nonce, and the full projection binding handle. Handles expose only a type
prefix plus the first 128 HMAC bits:

```text
prj_ clm_ ref_ prd_ val_ evd_ src_ + 32 lowercase hex characters
```

A global request-local collision table terminates if the same truncated handle
is derived from different local fingerprints. Top/load-bearing evidence and
lower-tier supporting evidence both receive opaque evidence handles. Counts
and arrays have strict inclusive maxima of 1023; the exact compact envelope
payload maximum is 4,194,303 bytes.

The nonce is request-scoped, but S5 has no durable nonce registry. A consumed
Rust permit cannot be reused through safe code, yet cross-process replay
prevention is not implemented and is not claimed.

## Authentication construction

The result records an envelope payload SHA-256 and transport HMAC. The payload
bytes are compact UTF-8 JSON emitted from fixed-order Rust structs by
`serde_json`. The precise profiles are:

```text
canonicalization = serde_json_compact_struct_field_order_utf8_v1
message_profile = u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json
domain = agent-bridge/track-b/candidate-evidence-envelope/v0
```

In expanded notation:

```text
payload_sha256 = SHA-256(exact_payload_json_bytes)
HMAC message = u64be(len(domain)) || domain
             || u64be(len(authentication_key_id)) || authentication_key_id
             || exact_payload_json_bytes
```

The transport key id is therefore a protected header even though it appears in
the outer authentication object. Key-id substitution changes the HMAC. A
golden vector, payload hash, and substitution negative case are tested.

This source interface does not expose payload bytes or an envelope serializer.
A future transport must verify received exact bytes rather than parse and
re-serialize them under an unspecified implementation.

## Truth and capacity invariants

Before authenticating a claim, S5 checks:

- `evidence_count == len(evidence_handles)`;
- `supported` has exactly one value handle;
- `conflicted` has at least two value handles;
- `unknown` has tier `none` and no value, evidence, supporting-evidence, or
  source-binding handles and zero evidence classification counts; and
- top, supporting, shadowed, noncurrent, value, and source-binding collections
  all remain below their exclusive internal sentinels.

The envelope reports the corresponding inclusive limits. A verifier must not
interpret the old internal sentinels as accepted maxima.

## Time and capability boundary

Issue and expiry values are non-negative signed 64-bit Unix timestamps in
seconds. Expiry is exclusive. The permit constructor bounds the TTL below the
3,600-second sentinel, and the binding call receives the actual evaluation time
and rejects expiry equality or later use.

The store feature `temporal-evidence-s5-candidate-synthetic` is absent from
default features and enables S4 plus the optional audited `ring` dependency.
The sole safe candidate-permit constructor is `#[cfg(test)]` and crate-private.
The pair constructor requires the unforgeable S4 permit, whose sole safe
constructor is also test-only. Enabling the feature in non-test code therefore
does not provide a safe way to create either capability.

Bridge contains only a feature-gated `pub(crate)` forwarding wrapper. There is
no CLI, MCP, daemon, StateStore, network, filesystem, candidate-context,
truth-manifest, or BioCortex runtime caller. The binding operation itself has no
external side effects.

## Verification matrix

Seven S5 tests cover:

1. deterministic opaque output, exact schema binding, top evidence handles,
   and absence of raw material from Debug output;
2. nonce changes across all request-scope bindings;
3. empty requests and ambient projected claims terminating the operation;
4. snapshot/prepared tuple mix-and-match despite equal projection digest;
5. replacement request/projection-pair mix-and-match, including equal visible
   projection output with a different prepared-input digest;
6. key equality, strict TTL sentinel, and bind-time expiry equality; and
7. independent framed-HMAC and authenticated-payload golden vectors, key-id
   substitution, and capacity-sentinel rejection.

The seven S4 tests and fourteen S2 temporal-ledger tests remain regression
gates. Low-memory validation uses one Cargo job, disabled incremental
compilation, disabled default ONNX features, one test thread, offline locked
dependencies, and stripped debug information.

These are correctness and boundary tests. S5 reports no latency, throughput,
memory-efficiency, model-quality, neuroscience, fermionic-algorithm, or
BioCortex performance gain.

## Remaining blockers

S5 resolves only the synthetic
`CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED` mechanism. Five independent gaps
remain:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

Additionally, no complete S5 source-artifact manifest, trial-specific artifact
manifest, candidate-context builder, final-context builder, truth manifest,
capture receipt, durable nonce registry, or production key-custody profile is
bound. No legacy row or trial is qualified. Side effects remain `NONE`.

## Next admissible step

S6 may preregister a transport and artifact-closure contract without activating
it. It must bind exact received envelope bytes, durable nonce/replay state,
trial identities, candidate-context construction, and a complete S5 source
manifest. Production admission still additionally requires separate authority,
capture, custody, privacy-deletion, and producer-profile evidence.
