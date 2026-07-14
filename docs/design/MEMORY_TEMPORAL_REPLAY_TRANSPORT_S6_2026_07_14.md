# Memory temporal replay transport S6

Date: 2026-07-14

Status:
`SYNTHETIC_DETACHED_VERIFIER_CONTRACT_IMPLEMENTED_NOT_TRANSPORT_NOT_DURABLE`

Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S6 closes two preregistration gaps without activating a transport:

1. it freezes the complete 14-path delta of the historical S5 feature commit;
2. it defines and executes, under a default-off test-only capability, the
   exact-byte authentication and atomic replay state machine expected of a
   future detached receiver.

It does not add a Bridge wrapper, StateStore surface, SQLite registry, MCP/CLI,
daemon, network or filesystem caller, payload exporter, BioCortex consumer, or
candidate-context builder. The authenticated S5 payload still says
`cross_repository_transport_authorized=false`, `live_binding_satisfied=false`,
and `side_effects_unlocked=NONE`. An S6 wrapper cannot override those protected
statements.

## The S5 split-wire correction

The S5 HMAC is computed over `CandidateEnvelopePayloadWire`. Those exact compact
JSON bytes do not contain the `authentication` object. The logical candidate
envelope schema, however, requires `authentication` at its top level. These are
compatible only when modeled as a detached join:

```text
S5 authentication metadata
        +
exact S5 payload bytes (no authentication field)
        =
logical candidate envelope
```

S6 therefore freezes the exact payload separately in
`biocortex-ab-track-b-candidate-exact-payload-profile-v0.json`. It is incorrect
to call the payload alone an instance of the logical envelope schema, and it is
incorrect to parse the payload, reserialize it, and authenticate the replacement
bytes. Authentication always uses the received bytes first. Reserialization is
used only afterward as a canonical-byte equality assertion.

The preregistered packet adds an authenticated route and canonical RFC 4648
padded base64 representation for a future cross-repository wire. This is a
test vector and contract, not a sender or receiver.

## Historical S5 source closure

The S5 source manifest binds:

```text
commit: 8739b69fb59fd704dacfe1a44bfc411ed9ebb913
parent: 486f04fb9a967a9a6cf5272f82f36cc0d7e787ad
tree:   d4ba782665fac2c55af60e1c0a988a327b3535dd
scope:  exact_s5_feature_commit_14_path_delta
count:  14
```

Every entry includes path, mode, byte count, SHA-256, and Git blob OID. The
checker independently derives the changed paths from Git and reads every
historical blob; it does not trust the manifest's self-reported list. The
manifest includes the S5 report itself and the sole executable mode on the S5
gate.

This proves only the content of the historical S5 feature commit. It does not
prove which source produced a current binary, which binary a remote party ran,
who held a key, or that a remote producer used this tree. Those require a build
attestation and producer/key-custody evidence. The S6 clean-HEAD gate binds the
manifest as an S6 artifact rather than attempting an impossible self-hash.

## Authentication profiles

S5 authenticates the exact payload with:

```text
HMAC-SHA-256(
  s5_transport_key,
  u64be(len(s5_domain)) || s5_domain ||
  u64be(len(s5_key_id)) || s5_key_id ||
  exact_payload_bytes
)
```

The future outer channel profile independently binds routing and source claims:

```text
HMAC-SHA-256(
  s6_channel_key,
  u64be(len(s6_domain)) || s6_domain ||
  u64be(len(channel_key_id)) || channel_key_id ||
  u64be(len(canonical_route_json)) || canonical_route_json ||
  exact_payload_bytes
)
```

The handle key, S5 transport key, and S6 channel key are distinct in the
synthetic vector. The route binds source and destination repository identities,
the historical source manifest, source commit/tree, all relevant Track B schema
digests, the detached S5 authentication metadata, the full trial identity,
time window, payload length/digest, projection handle, and every closed boundary
bit. A packet's source-manifest claim is not a trust root: a future receiver must
pin it from an external allowlist.

The deterministic synthetic vector contains a 2,182-byte exact payload. The
standard-library checker independently recomputes its payload SHA-256 and both
HMACs. The store-local Rust executable contract independently exercises the S5
detached exact-payload HMAC, strict parse, identity join, and replay transition;
it is deliberately not an outer route receiver.

## Required verification order

The order is normative:

```text
bounded outer decode
-> exact payload length and SHA-256
-> outer route + exact-payload HMAC
-> detached S5 exact-payload HMAC
-> strict payload parse and canonical byte equality
-> inner/outer identity join
-> injected evaluated_at / strict TTL check
-> derive replay identity and scope commitment
-> one atomic consume_once
-> release a private verified token
```

Payload parsing before both exact-byte authenticators is forbidden. Authenticating
a parse/reserialize replacement is forbidden. Equality at the 4 MiB and 3,600
second sentinels is rejection, and expiry equality is rejection.

The default-off Rust module is a local executable specification only. Its module
is private, its types are crate-private or narrower, its permit constructor and
registry constructor exist only under `cfg(test)`, and nothing is re-exported.
The verifier consumes owned bytes to avoid caller mutation, retains them only in
a private non-cloneable/non-serializable token, and exposes no bytes getter. No
runtime path can construct its capability.

## Replay contract

The replay uniqueness key is the domain-separated commitment of:

```text
(s5_transport_key_id, request_nonce)
```

Trial ID is deliberately not part of uniqueness. Otherwise one transport key
could reuse a nonce merely by changing trials. A separate scope commitment binds
the S5 source manifest, payload profile, handle-key ID, trial, contract, case,
request, projection handle, time window, and payload digest.

The atomic operation is `consume_once`:

- an unseen uniqueness key is inserted with its scope commitment;
- the same key and commitment is `REPLAY`;
- the same key with another commitment is `SCOPE_COLLISION`;
- neither rejection changes the first reservation.

S6 supplies only a mutex-protected, process-local synthetic registry for hostile
tests. It is not durable and cannot prove restart, crash, or multi-process replay
safety. A future durable implementation must be insert-only, must preserve a
burned nonce after expiry, and must fail closed on an indeterminate commit result.

## Track B compatibility boundary

S6 pins the identity-composition manifest, truth-manifest schema, review schema,
candidate schema, foundational manifest, and truth-referent schema. This is an
artifact compatibility binding, not a live artifact binding.

The S5 payload shares the `clm_`, `ref_`, and `prd_` referent spine with Track B,
but it does not supply `ast_` assertion handles, authority/currentness basis
digests, a gold evidence slice, private map/custody receipts, selected-case
producer identity, or expected response mode. A `val_` handle cannot be renamed
to an `ast_` handle. Consequently no truth manifest, candidate context, final
context, review readiness, or live ledger binding is claimed.

## Verification matrix

The checker and Rust tests reject:

- incomplete, duplicate, reordered, path-traversing, wrong-mode, wrong-hash,
  wrong-parent, wrong-tree, or wrong-commit S5 source manifests;
- one-byte payload changes, whitespace substitutes, key-order substitutes,
  duplicate keys, invalid UTF-8, invalid/noncanonical base64, length/digest
  mismatches, and exact-cap equality;
- S5 domain/key/profile changes and S6 source, destination, source-manifest,
  channel-key, route, or HMAC substitutions;
- inner/outer trial, contract, case, request, nonce, time, digest, and projection
  mismatches;
- future issue time, expiry equality, invalid TTL, and opened inner or outer
  boundaries; and
- exact replay and same-key/nonce scope collision without corrupting the first
  reservation.

S5, S4, and S2 regressions remain gates. Builds use one Cargo job, disabled
incremental compilation, disabled default ONNX features, stripped debug data,
offline locked dependencies, and one test thread.

These are correctness and boundary results. S6 reports no model-quality,
latency, throughput, memory-efficiency, neuroscience, BioCortex, or fermionic
algorithm performance improvement.

## Remaining blockers

The original five blockers remain unchanged:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

Additionally, durable replay, build/producer identity, an authorized payload
version, candidate/truth/final-context builders, capture receipts, and runtime
source bindings remain absent. Side effects remain `NONE`.

## Next admissible step

The next step is not to attach this verifier to Bridge. First freeze an
authorized successor payload/version and its authority/custody decision, then
implement a durable content-free replay tombstone registry with crash/restart
tests and externally pinned producer/build provenance. Only after those gates
may a separate review consider a default-off Bridge shadow caller. Production
or BioCortex influence remains independently blocked.
