# Free Recall Strategy R4 — Observation-Only Integration Preregistration

Date: 2026-07-21

Status: **PREREGISTERED / DESIGN-ONLY / PUBLIC-SYNTHETIC / DEFAULT-OFF**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R3_PROSPECTIVE_EPISODE_SIDECAR_RESULT_2026_07_21.md`

## 1. Question

R3 proved that an explicit episode event stream can be reduced deterministically
and fail closed under a public-synthetic fault model. R4 asks whether that
contract can be mapped onto Agent-Bridge as an additive observation surface
without coupling it to `MemoryRecord`, current retrieval, MCP write tools,
session lifecycle truth, private content, or default runtime behavior.

R4 is a design-admission experiment. It does not create the table or producer
described below.

## 2. Source-grounded seam decision

The current store keeps memory content and retrieval fields in `memories`, with
FTS triggers tied directly to that table. `session_curate` extracts and persists
multiple `MemoryRecord` values and separately emits a best-effort semantic
lifecycle event describing whether curation persisted anything.

Therefore:

- do not add episode fields to `MemoryRecord` or `memories`;
- do not treat the existing `session_curate` semantic event as episode
  membership or order;
- do not attach FTS, vector, graph, coactivation, or retrieval triggers to the
  episode sidecar;
- if a later implementation is authorized, use one separate append-only event
  table and derive finalized bundles read-only.

## 3. Frozen design contract

Contract version: `agent_bridge.episode_observation_integration.v0`.

The design manifest must declare:

- `mode = "disabled"`;
- `default_enabled = false`;
- `producer_enabled = false`;
- `retrieval_consumer_enabled = false`;
- `mcp_surface_enabled = false`;
- `real_capture_allowed = false`;
- `storage_mutation_allowed = false`;
- `deployment_allowed = false`.

The proposed append-only relation is named
`episode_observation_events` and contains only:

- `event_id`: globally unique opaque identifier;
- `episode_id`: opaque identifier;
- `event_type`: `episode.open`, `episode.item`, or `episode.close`;
- `source_kind`: `session`, `curation_batch`, or `owner_bundle`;
- `producer_run_id`: opaque producer-attempt identifier;
- `item_ref`: nullable, domain-separated opaque reference for item events;
- `episode_position`: nullable non-negative integer for item events;
- `item_count`: nullable non-negative integer for close events;
- `payload_sha256`: canonical event-payload commitment;
- `observed_at`: append time, never ordering authority.

No column may contain memory content, conversation text, query text, tags,
embedding bytes, raw memory keys, scopes, related keys, rank scores, or user
identity. `item_ref` is an abstract boundary in R4; its concrete derivation,
key custody, rotation, and join procedure require a later security review.

## 4. Projection and authority contract

The proposed reader:

- uses the R3 reducer semantics unchanged;
- orders only by declared `episode_position`, never by `observed_at` or row ID;
- emits only complete, conflict-free finalized bundles;
- returns no bundle on absence, ambiguity, conflict, or incompleteness;
- cannot read or mutate retrieval indexes;
- cannot influence search results, ranking, memory writes, consolidation,
  coactivation, training, or BioCortex;
- exports aggregate counters only in R4 fixtures.

The manifest must define a kill switch whose disabled state means zero producer
calls, zero sidecar writes, zero projection reads by retrieval, and zero output
differences in existing memory APIs.

## 5. Public-synthetic design fixtures

The offline validator receives one canonical manifest and directed mutations:

1. enable each authority flag independently;
2. change mode from `disabled`;
3. add each forbidden content/identity/retrieval field;
4. attach a retrieval, FTS, vector, graph, or memory-write consumer;
5. make time or row ID an ordering authority;
6. permit partial or ambiguous bundles;
7. claim real-session capture or deployment authority;
8. remove the kill switch or any zero-effect invariant;
9. replace the independent relation with a `MemoryRecord` field;
10. claim `item_ref` derivation or custody is already solved.

The validator is standard-library-only, deterministic, and performs no DB,
network, MCP, environment, clock, or private-data access.

## 6. Gates

### Isolation gate

- canonical manifest passes;
- all authority flags remain false and mode remains disabled;
- relation is separate from `memories` and has no retrieval trigger/consumer;
- allowed columns match the frozen set exactly;
- recursively forbidden fields are rejected.

### Fail-closed gate

- projection requires complete, unique, contiguous membership;
- absence, ambiguity, conflict, and incompleteness all abstain;
- time and storage order have no ordering authority;
- disabled mode declares zero effects on existing APIs and retrieval output.

### Mutation gate

Every directed mutation fails for the intended reason, while permutation of
JSON object keys leaves the canonical verdict and digest unchanged.

### Determinism gate

Independent runs emit byte-identical aggregate reports.

## 7. Decision rule

- If every gate passes, R4 may publish a design verdict and propose R5 as a
  separately authorized source-only implementation plan.
- If isolation or fail-closed gates fail, stop and revise the contract.
- R5 must separately decide `item_ref` derivation/custody before any source is
  accepted; R4 does not silently choose a security mechanism.

## 8. Negative authority

R4 does not authorize a SQLite migration, `StateStore` API, producer,
projection implementation, MCP tool, real-session capture, retrieval consumer,
build, test against private state, execution, deployment, training, or
BioCortex use.
