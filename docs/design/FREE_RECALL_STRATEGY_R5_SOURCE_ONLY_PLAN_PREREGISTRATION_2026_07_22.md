# Free Recall Strategy R5 — Source-Only Plan Preregistration

Date: 2026-07-22

Status: **PREREGISTERED / DESIGN AND OFFLINE VALIDATION ONLY / NO SOURCE AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R4_OBSERVATION_ONLY_INTEGRATION_RESULT_2026_07_21.md`

## 1. Question

R5 asks whether the R4 observation-only contract can be decomposed into a
small, reviewable source sequence with a concrete `item_ref` construction,
explicit migration and rollback semantics, one producer seam, and strict
separation between source, build, execution, real capture, retrieval, and
deployment authority.

R5 validates the plan. It does not implement the plan.

## 2. `item_ref` decision

### Rejected candidates

- raw memory key: directly discloses canonical identity;
- unkeyed SHA-256: permits dictionary matching against enumerable memory keys;
- random handle: requires a second persistent key-to-handle mapping or a field
  on `MemoryRecord`, reintroducing the coupling rejected by R4;
- ciphertext: adds reversible plaintext recovery and broader key-management
  requirements without helping the observation-only use case.

### Selected construction

`item_ref` is a full-length HMAC-SHA-256 pseudonym:

```text
item_ref = "epr_v1_" || key_epoch || "_" || lower_hex(
  HMAC-SHA-256(K_epoch,
    frame("agent-bridge/episode-item-ref/v1") ||
    frame(memory_key_utf8)
  )
)
```

`frame(x)` is an unsigned 64-bit big-endian byte length followed by exact bytes.
The output is not truncated. `key_epoch` is a non-secret opaque identifier and
is authenticated inside the HMAC frame as well as carried in the textual
prefix; substitution must fail.

The construction follows the keyed-hash model of RFC 2104. The proposed Rust
source should use a reviewed HMAC implementation compatible with the existing
`sha2 = 0.10` dependency rather than a handwritten MAC.

## 3. Key-provider boundary

The source slice accepts key material only through an internal
`EpisodeRefKeyProvider` interface. It must not:

- read a secret from an environment variable or command-line argument;
- auto-generate or persist a production key;
- log, serialize, clone into reports, or expose key bytes;
- silently fall back to an unkeyed digest;
- accept fewer than 32 bytes of key material;
- select an epoch from untrusted event input.

R5 freezes only the interface and synthetic test provider. Production key
provisioning, filesystem/OS-keystore custody, backup, recovery, and first
enablement require a later security and owner gate. With no trusted provider,
the only valid state is disabled and no events are emitted.

Rotation is explicit: new events use the provider's active epoch; read-only
offline joins may use a bounded provider-approved set of retained epochs. An
unknown or unavailable epoch abstains. Existing events are never rewritten.

## 4. Retention and deletion refinement

Normal event ingestion remains append-only. R5 adds one narrow lifecycle
exception to R4: an explicit whole-episode purge may delete all events for an
episode in one transaction. Partial row deletion is forbidden. Purge is not a
retrieval operation and cannot be inferred from similarity.

No purge implementation is authorized here. Before real capture, a later gate
must bind purge initiation to actual memory-deletion policy and prove that
backups, exports, retained epoch keys, and sync peers do not create a false
erasure claim.

## 5. Proposed source sequence

### Slice A — pure contract types and pseudonym derivation

- private module under `ab-store`;
- event/type validation and canonical framing;
- `EpisodeRefKeyProvider` trait and synthetic provider in tests only;
- HMAC known-answer, domain-separation, epoch-substitution, Unicode-byte,
  empty/oversized input, unknown-epoch, and no-key fail-closed tests;
- a no-op sink whose calls produce no writes or observable output changes.

Slice A contains no SQLite code, feature enablement, producer call site, MCP
surface, or runtime configuration loader.

### Slice B — disposable-database migration and inert store adapter

- a separate `episode_observation_events` relation using the next schema
  version current at implementation time; R5 does not reserve a number;
- exact R4 columns and check constraints, with no foreign key to `memories`;
- primary key on `event_id` and a lookup index on `episode_id` only;
- no FTS, vector, graph, coactivation, sync, export, or retrieval trigger;
- internal append and finalized-projection methods behind both compile-time and
  runtime default-off gates;
- migration tests on new and upgraded disposable databases;
- rollback means disable producer and reader while leaving the inert relation;
  dropping a populated table is a separate destructive gate.

Slice B is not authorized by R5 completion.

### Slice C — one explicit producer seam

The first candidate producer is `session_curate`, classified as
`source_kind = curation_batch`:

- open immediately before its candidate-save loop;
- emit an item only after the corresponding memory save succeeds;
- close after the loop with the count of successfully emitted items;
- preserve saved-candidate order as declared episode position;
- crash or write failure leaves an incomplete episode, which the projection
  must ignore;
- zero successful saves produce no finalized episode;
- producer activation requires both compile-time support and an explicit
  runtime flag plus a trusted key provider.

No inferred session grouping, hooks, `memory_save`, or owner bundle producer is
in the first slice.

Slice C is not authorized by R5 completion.

## 6. Offline join boundary

A later bounded audit may derive HMAC references for current memory keys under
provider-approved epochs and join them to finalized episode items entirely in
process. It must not persist a reverse map, expose raw keys in reports, or feed
search/ranking. Missing key epochs, collisions, duplicate matches, or ambiguous
episodes abstain.

This O(number of memories × retained epochs) operation is suitable only for a
bounded offline audit, not a retrieval hot path.

## 7. Plan gates

The offline R5 validator must reject directed mutations that:

- choose raw, unkeyed, random-mapping, truncated, or reversible references;
- remove domain/length framing or epoch authentication;
- permit environment/CLI secrets, auto-generation, weak keys, logging, or
  unkeyed fallback;
- reserve a schema version, modify `MemoryRecord`, add a foreign key, trigger,
  sync/export path, retrieval consumer, or default-on flag;
- permit partial purge, event rewrite, unknown-epoch fallback, reverse-map
  persistence, or non-abstaining ambiguity;
- add another producer or claim source/build/run/capture/deploy authority.

Object-key permutations must preserve the canonical digest. Independent runs
must emit byte-identical aggregate reports.

## 8. Decision rule

- If all gates pass, R6 may request separate owner authorization for Slice A
  source only.
- Slice A acceptance does not open Slice B; Slice B acceptance does not open
  Slice C.
- Build, execution, real capture, retrieval experiment, merge, deployment, and
  production key provisioning remain independent gates.

## 9. Negative authority

R5 does not authorize dependency changes, Rust source, migrations, database
access, key generation or custody, producers, builds, tests involving private
state, execution, real capture, retrieval changes, merge, deployment,
training, or BioCortex.

## 10. Primary references

- RFC 2104, *HMAC: Keyed-Hashing for Message Authentication*:
  <https://www.rfc-editor.org/rfc/rfc2104>
- NIST Message Authentication Codes publication index:
  <https://csrc.nist.gov/Projects/message-authentication-codes/publications>
- RustCrypto `hmac` documentation:
  <https://docs.rs/hmac/0.12.1/hmac/>
