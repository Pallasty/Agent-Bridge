# Live Semantic World Runtime - Core Extraction Criteria

**2026-06-06 - role: P5 core extraction gate**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Human input mapping](LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md)
- [Nexus seed pressure](LIVE_SEMANTIC_WORLD_RUNTIME_NEXUS_SEED_PRESSURE_2026_06_06.md)

Forum anchors:
- `#105` post `#2554`: P5 start notice.

## 0. Status

This document is docs-only. It does not implement `world-core`, modify
`crates/bridge`, resume Step D, register MCP tools, or open #92/#94 wiring.

The goal is to define the bar for extracting shared LSWR core concepts from
seed-specific proofs.

## 1. Extraction Thesis

Do not extract LSWR core from one seed.

An object, field, API, event type, or verification method may enter shared core
only when it survives both current seed pressures:

```text
Onsen: spatial/visual live-world proof
Nexus: event/causal/governance/replay proof
```

If a concept only proves useful in one seed, it remains adapter-specific
evidence until another seed proves it general.

## 2. Mandatory Core Tests

Every core candidate must pass all tests below.

| Test | Requirement |
|---|---|
| `CORE-001` | Stable identity across API calls, events, feedback, and verification |
| `CORE-002` | Usable by both human-facing and AI-facing surfaces |
| `CORE-003` | Does not depend on screenshots, editor GUI automation, or a specific engine |
| `CORE-004` | Can carry `verified`, `not_verified`, and `blocked` without ambiguity |
| `CORE-005` | Does not improve lower-layer truth at a higher layer |
| `CORE-006` | Allows adapter-specific evidence without promoting it to global schema |
| `CORE-007` | Supports branch, timeline, or replay context where needed |
| `CORE-008` | Has a useful query path for agents |
| `CORE-009` | Has a useful presentation or review path for humans |
| `CORE-010` | Can fail honestly with stable reason codes |

Failing any mandatory test means the candidate stays out of core.

## 3. Object Admission Matrix

### 3.1 Admit To Core Now

These concepts are already supported by both Onsen and Nexus pressure.

| Core object | Admission reason | Minimum fields |
|---|---|---|
| `World` | Both seeds need a stable session root and timeline | `world_id`, `adapter`, `time`, `branch_id`, `constraints` |
| `Entity` | Both seeds need stable referents | `entity_id`, `kind`, `state`, `tags`, `refs` |
| `Participant` | Both seeds need actor/source identity | `participant_id`, `kind`, `authority_mode`, `surface` |
| `Action` | Onsen has patches; Nexus has commands | `action_id`, `kind`, `source`, `target_refs`, `expected_effect`, `rollback_group` |
| `Event` | Both seeds need world history | `event_id`, `event_type`, `world_id`, `source`, `refs`, `payload`, `provenance` |
| `Feedback` | Both seeds need responses anchored to world refs | `feedback_id`, `source_event_id`, `target`, `raw`, `normalized` |
| `Verification` | Both seeds need honest evidence verdicts | `verdict`, `reason`, `method`, `verified_to`, `evidence` |
| `Branch` or `Timeline` | Both seeds need alternate trajectory language | `branch_id`, `parent_branch_id`, `source_action_id`, `time_range` |
| `AdapterEvidence` | Both seeds need seed-specific proof payloads | `adapter_kind`, `method`, `summary`, `raw_available`, `payload` |

`Action` is the preferred shared term for the patch/command layer. Adapter APIs
may keep sharper words such as `Patch` or `Command`.

### 3.2 Keep As Provisional Core

These may be core, but need stricter naming or one more seed before
implementation.

| Candidate | Current pressure | Provisional decision |
|---|---|---|
| `Space` | Onsen needs space; Nexus needs causal/economic scope | Rename pressure toward `Scope` before core extraction |
| `Snapshot` | Onsen can export scene/render state; Nexus can export Arrow/replay state | Core only as opaque snapshot ref and comparison result |
| `Effect` | Both seeds need expected vs observed effects | Core as query/result concept, not a fixed effect taxonomy |
| `MemoryLink` | Both seeds may link durable memory | Keep optional; do not couple to one memory substrate |

### 3.3 Keep Adapter-Specific

These are valid but not shared core.

| Adapter concept | Keep out of core because |
|---|---|
| `viewport`, `screen_area`, `pixel_coverage` | Onsen visual evidence only |
| `bounds_screen_area`, `alpha`, `occlusion` | Onsen render-specific |
| `event_hash`, `prev_hash`, `verify_chain` | Nexus integrity evidence |
| `causal_edge`, `influence_score`, `subgraph_around` | Nexus causal evidence |
| `Arrow RecordBatch`, SQL/DuckDB export | Nexus transport/export evidence |
| `governance_decision` synthetic node | Nexus governance audit evidence |
| `seed_runtime` metrics | Nexus/AiOT attention evidence |
| engine-specific scene nodes | presentation implementation detail |

Adapter-specific does not mean unimportant. It means the payload belongs inside
`Verification.evidence` or `AdapterEvidence`, not in the global object model.

## 4. API Admission Matrix

### 4.1 Core API Candidates

| API | Admission status | Reason |
|---|---|---|
| `world.get` | admit | Both seeds need session/root state |
| `world.query` | admit | Both seeds need semantic search over world refs |
| `world.apply` | admit | Shared action entry point for patch/command |
| `world.events.query` | admit | Both seeds need history query |
| `world.feedback.query` | admit | Both seeds need response query |
| `world.evidence.query` | admit | Generalizes visibility, causal, replay, and hash evidence |
| `world.effect.query` | provisional | Useful, but expected-effect grammar needs another pass |
| `world.branch.create` | provisional | Onsen branch and Nexus replay/counterfactual both need it, but implementation differs |
| `world.branch.compare` | provisional | Same as above |
| `world.rollback` | provisional | Must not assume engine-specific save/load |
| `world.snapshot.export` | provisional | Core only as opaque snapshot contract |
| `world.snapshot.compare` | provisional | Needs common diff envelope |

`world.apply` should not erase adapter vocabulary. A world adapter may expose
`world.patch` or `world.command` internally, but the core product contract should
name the shared intent as applying an action.

### 4.2 Adapter API Candidates

| API | Adapter |
|---|---|
| `onsen.visibility.query` | Onsen |
| `onsen.render.query` | Onsen |
| `nexus.causality.query` | Nexus |
| `nexus.event_store.query` | Nexus |
| `nexus.replay.compare` | Nexus |
| `nexus.governance.audit` | Nexus |

These may be wrapped by `world.evidence.query`, but they should not become
global verbs until another seed needs the same exact method.

## 5. Verification Admission Rules

`Verification` is core. Individual methods are adapter-specific.

Allowed core verdicts remain:

```text
verified
not_verified
blocked
```

Core fields:

| Field | Core rule |
|---|---|
| `verdict` | Required; one of the three allowed verdicts |
| `reason` | Required for `not_verified` and `blocked` |
| `method` | Required when evidence is present |
| `verified_to` | Non-null only for `verified` |
| `evidence` | Adapter-specific payload; never omitted when a claim is made |

Adapter evidence examples:

| Method | Adapter | Evidence |
|---|---|---|
| `live_viewport_pixel_coverage` | Onsen | screen area, bounds area, host reason |
| `nexus_event_hash_chain` | Nexus | event ID, hash-chain status |
| `nexus_causal_edge` | Nexus | cause, consequence, edge type |
| `nexus_replay_compare` | Nexus | replay source, deterministic status, divergence |
| `human_review_decision` | human surface | control ID, decision event, target event |

Core must never infer that a human accept event turns a failed adapter
verification into success.

## 6. Event Schema Admission Rules

P2's event envelope is admitted as a core draft with additive refinements.

Keep:

- `schema`;
- `event_id`;
- `event_type`;
- `world_id`;
- `branch_id`;
- `tick` or monotonic sequence;
- `created_at`;
- `source`;
- `refs`;
- `payload`;
- `verification`;
- `provenance`.

Additive pressure from P5:

| Field | Rule |
|---|---|
| `refs.entities` | Core |
| `refs.scopes` | Prefer over spatial-only `spaces` in future core |
| `refs.events` | Core |
| `refs.actions` | Core |
| `refs.feedback` | Core |
| `refs.snapshots` | Provisional |
| `refs.adapter` | Core as adapter ref, not adapter payload |
| `provenance.adapter` | Core |
| `provenance.source_schema` | Core |
| `provenance.raw_available` | Core |

Do not delete older fields immediately. The next schema revision can introduce
`refs.scopes` while allowing `refs.spaces` as an Onsen-compatible alias.

## 7. Human Surface Admission Rules

Human-facing controls are not automatically core. Their events may be core.

Admit to core event semantics:

- `human.click`;
- `human.hover_or_dwell`;
- `human.move_path`;
- `human.select`;
- `human.accept`;
- `human.reject`;
- `human.note`;
- `runtime.rollback_applied`.

Keep surface-specific:

- exact mouse/keyboard device protocol;
- viewport coordinates;
- UI control IDs;
- card layout;
- color treatment;
- HTML render artifact internals;
- game-engine node paths.

Rule: core records what happened and what it referenced. The adapter records how
the concrete surface captured it.

## 8. Extraction Blockers

The following are hard blockers for moving a candidate into core:

| Blocker | Meaning |
|---|---|
| `single_seed_only` | Candidate only works for Onsen or Nexus |
| `truth_laundering` | Candidate can turn lower-layer failure into success |
| `engine_embedded` | Candidate embeds a concrete engine or GUI workflow |
| `evidence_erased` | Candidate drops stable reasons or adapter evidence |
| `human_surface_erased` | Candidate cannot explain the result to humans |
| `agent_query_erased` | Candidate cannot be queried by agents |
| `authority_ambiguous` | Candidate lacks participant/authority mode |
| `rollback_unsafe` | Mutating action has no rollback/branch story |
| `adapter_unavailable_success` | Unavailable adapter can look successful |
| `profile_creep` | Candidate widens user-facing tools before acceptance |

## 9. Acceptance Falsifiers

Any proposed `world-core` extraction fails if one of these holds:

| ID | Falsifier |
|---|---|
| `CE-001` | Onsen `not_verified` result becomes `verified` after presentation |
| `CE-002` | Nexus accepted command has no event evidence but core marks success |
| `CE-003` | Human accept rewrites lower-layer verification |
| `CE-004` | Core schema requires viewport fields for Nexus |
| `CE-005` | Core schema requires causal graph fields for Onsen |
| `CE-006` | Adapter unavailable returns an empty success-like ACK |
| `CE-007` | Reason is only present in raw payload and disappears when raw is hidden |
| `CE-008` | Event cannot be tied back to participant or authority mode |
| `CE-009` | Branch/replay context is impossible to represent |
| `CE-010` | Proposed API cannot return `blocked` distinctly from `not_verified` |
| `CE-011` | Evidence is not queryable by an agent |
| `CE-012` | Evidence is not presentable to a human reviewer |

## 10. Implementation Sequencing

P5 recommends this order for later implementation:

1. Write a versioned `world-core` schema draft as docs, not code.
2. Define one neutral `world.evidence.query` envelope.
3. Map current Step C `world_query`, `world_patch`, and
   `world_visibility_query` into that envelope without renaming live tools.
4. Add Nexus-style fixture examples for event/causal/replay evidence.
5. Only then consider a Rust data model crate.

Do not implement `world-core` directly from this document. This is an admission
gate, not the schema itself.

## 11. P6 Recommendation

The next package should refresh the engine/API research against the new criteria:

- Bevy, Fyrox, Godot, and custom Rust runtime are evaluated as adapters or
  presentation/runtime hosts, not as the core.
- The question changes from "which engine can AI drive?" to "which adapter can
  expose stable world state, events, evidence, human feedback, and rollback
  without making screenshots the primary perception layer?"
- The output should be a shortlist of viable adapter stacks and the evidence
  each can produce.
