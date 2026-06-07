# Live Semantic World Runtime - Requirements v1

**2026-06-06 - role: product requirements**

Parent documents:
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Live Semantic World Runtime v0 review](LIVE_SEMANTIC_WORLD_RUNTIME_V0_REVIEW_2026_06_04.md)
- [Phase 0 Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_SPEC_2026_06_04.md)
- [Phase 0 Step B Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_B_SPEC_2026_06_05.md)
- [Phase 0 Step C Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_C_SPEC_2026_06_05.md)

Forum anchors:
- `#102`: Phase 0 A/B/C accepted.
- `#104`: session identity hardening closed at `ca4dfbb`.
- `#105`: mainline planning; Step D D1 is accepted but halted and is not a
  current implementation dependency.

## 0. Status

This is a requirements document, not an implementation plan.

It consolidates the original research direction into a product contract for a
future runtime. It deliberately does not resume the halted Step D line, register
new MCP tools, or move any `crates/bridge` code.

## 1. Product Definition

The Live Semantic World Runtime is:

> A runtime-mediated interaction form where humans and AI agents mutate,
> perceive, verify, and discuss one shared semantic world through different
> expression surfaces.

It is not first a 3D engine, editor, game, or asset pipeline. A 3D or 2D client
is one presentation surface for a shared semantic state.

### REQ-PROD-001: Shared semantic world

The system MUST maintain a single semantic world state that both humans and AI
agents can reference through stable object identities.

### REQ-PROD-002: Different expression surfaces

The system MUST allow different participants to interact through different
surfaces:

- AI agents through structured APIs;
- humans through live visual interaction, review controls, and text feedback;
- future systems through events, memory, dashboards, or exported artifacts.

### REQ-PROD-003: Runtime, not editor automation

The AI interaction path MUST be semantic patch/query/event APIs. It MUST NOT
depend on the AI driving editor GUI controls as the primary design mechanism.

## 2. Participant Roles

The runtime MUST support role changes during a session.

Human roles:

- player;
- collaborator;
- director;
- reviewer;
- influence source.

AI roles:

- creator;
- editor;
- observer;
- simulator;
- critic;
- negotiator.

### REQ-ROLE-001: Explicit participant identity

Every patch, event, feedback item, and verification record MUST carry a
participant identity or runtime source.

### REQ-ROLE-002: Explicit authority mode

Every session MUST declare the current AI authority mode:

| Mode | AI authority |
|---|---|
| `observe` | Read-only |
| `suggest` | Propose patches |
| `coedit` | Apply reversible patches |
| `autonomous` | Apply patches continuously |
| `locked` | No mutation |

### REQ-ROLE-003: Mutating actions are reversible

Any mutating AI action in `coedit` or `autonomous` mode MUST carry:

- reason;
- affected entities;
- expected effect;
- rollback group;
- before/after diff;
- verification result or pending verification marker.

## 3. Runtime Session Loop

The runtime MUST support this loop:

```text
AI proposes or applies semantic patch
  -> world adapter mutates live state
  -> human-visible surface changes or fails
  -> runtime emits structured perception, events, and verification
  -> human accepts, rejects, annotates, or keeps interacting
  -> AI revises, explains, branches, or rolls back
```

### REQ-LOOP-001: Patch result is never empty ACK

A patch response MUST include:

- whether the operation was attempted;
- whether it was applied;
- before/after state where available;
- affected entity IDs;
- verification status;
- machine-readable reason when not verified or blocked.

### REQ-LOOP-002: Human-visible result is a first-class concern

The runtime MUST distinguish logical mutation from human-visible change. A
logical patch that does not affect the human-visible surface MUST NOT be reported
as a verified human-visible success.

### REQ-LOOP-003: Structured perception first

The AI's primary perception MUST be structured world/render/event data.
Screenshots MAY be used for audit, calibration, regression, or visual review,
but MUST NOT be the main perception substrate.

## 4. Core World Objects

The minimum shared model SHOULD include:

| Object | Purpose |
|---|---|
| `World` | Session root, time, active branch, constraints |
| `Entity` | Stable semantic object with role, tags, components, state |
| `Space` | Region, room, path, viewport, zone, graph, or causal scope |
| `Participant` | Human or AI actor |
| `Patch` | Atomic semantic mutation |
| `Event` | Runtime event from patch, human input, render, adapter, or system |
| `Feedback` | Human or AI response anchored to world references |
| `Verification` | `verified`, `not_verified`, or `blocked` evidence record |
| `Branch` | Alternative world trajectory |
| `RollbackGroup` | Reversible set of patches |
| `MemoryLink` | Optional reference to durable memory or training stream |

### REQ-WORLD-001: Stable references

World objects MUST have stable IDs usable across API calls, events, feedback,
verification records, and presentation artifacts.

### REQ-WORLD-002: Seed-specific evidence

The model MUST allow adapter-specific evidence without making that evidence
global core schema. For example, Onsen may carry screen-area evidence; Nexus may
carry causal-event evidence.

### REQ-WORLD-003: Branch-awareness

State, patches, events, feedback, and verification records SHOULD include branch
or timeline context once branch/rollback exists.

## 5. Agent API Requirements

The long-term agent surface SHOULD provide:

```text
world.get
world.query
world.patch
world.visibility.query
world.events.query
world.events.subscribe
world.feedback.query
world.branch.create
world.branch.compare
world.rollback
world.snapshot.export
```

Phase 0 accepted only the first concrete slice:

```text
world_query
world_patch
world_visibility_query
```

### REQ-API-001: Adapter client boundary

Agent-facing tools SHOULD be thin clients of world adapters. Agent-Bridge MUST
NOT embed a concrete game engine merely to expose the API.

### REQ-API-002: Honest unavailable-world result

If a world adapter is unavailable, timed out, malformed, or cannot provide
evidence, the API MUST return structured `not_verified` or `blocked` results.
It MUST NOT return a successful-looking empty response.

### REQ-API-003: Profile safety

Experimental world tools MUST remain out of default user-facing tool profiles
until their human and safety surfaces are accepted.

### REQ-API-004: Queryable reasons

`not_verified` and `blocked` results MUST carry stable top-level reasons and
evidence-level reasons where available. The reason MUST survive raw-detail
stripping.

## 6. Human Surface Requirements

The first human surface SHOULD be a live viewer, not a full editor.

Required capabilities:

- visible world surface;
- mouse and keyboard interaction;
- object focus or selection;
- accept/reject controls for proposed changes;
- short text feedback;
- visible change markers when AI mutates state;
- undo/revert affordance;
- branch compare/select once branches exist;
- visible verification status for AI claims.

### REQ-HUMAN-001: Human feedback is anchored

Human feedback SHOULD be anchored to entity, space, event, patch, branch, or
viewport context whenever possible.

### REQ-HUMAN-002: Human acceptance does not rewrite evidence

If a human accepts a presentation of a world result, the system MUST record
"human accepted this presentation" separately from lower-layer world
verification. Human acceptance MUST NOT convert `not_verified` into `verified`.

### REQ-HUMAN-003: Human-visible side effects are explicit

If runtime perception disturbs the human-visible surface, the disturbance MUST
be measured or reported. Phase 0's live-viewport flicker accounting is the
reference precedent.

## 7. Event And Feedback Bus Requirements

The runtime SHOULD capture a structured event stream.

Minimum event families:

```text
human.move_path
human.click
human.hover_or_dwell
human.select
human.accept
human.reject
human.note
ai.patch_proposed
ai.patch_applied
runtime.visibility_measured
runtime.verification_result
runtime.branch_created
runtime.rollback_applied
```

### REQ-EVENT-001: Event envelope

Every event SHOULD include:

- event ID;
- schema version;
- participant or source;
- world ID;
- branch or timeline ID when available;
- timestamp or tick;
- entity references where available;
- viewport or camera reference when relevant;
- cause event or patch reference where relevant.

### REQ-EVENT-002: Feedback normalization

The runtime SHOULD preserve raw human feedback and, when possible, add a
normalized semantic interpretation. The raw feedback MUST remain recoverable.

### REQ-EVENT-003: Replayability

Event order SHOULD be recoverable enough to explain how a world state, feedback
record, or verification result was reached.

## 8. Verification Ledger Requirements

The runtime MUST use three top-level verdict families:

| Verdict | Meaning |
|---|---|
| `verified` | Evidence confirms the claim in the relevant world/render context |
| `not_verified` | Evidence contradicts the claim or cannot confirm it |
| `blocked` | The runtime could not safely attempt the operation |

### REQ-VERIFY-001: No green-but-inert

A world change that is invisible to the human-visible surface MUST NOT be
reported as a human-visible success.

### REQ-VERIFY-002: Render-grounded visual claims

For spatial/visual worlds, visibility and readability claims MUST derive from
the same render pipeline the human sees, not from a parallel proxy or logical
state dictionary.

### REQ-VERIFY-003: Falsifiable expected effects

Every patch expected effect SHOULD be expressible as a falsifiable clause. If
the effect cannot be evaluated, the result MUST be `not_verified`, not success.

### REQ-VERIFY-004: Truth does not improve across layers

A later layer such as presentation, human review, memory, or training ingestion
MUST NOT upgrade lower-layer `not_verified` evidence into `verified`.

### REQ-VERIFY-005: Evidence shape

Verification records SHOULD preserve:

- method;
- verified target;
- measured values;
- adapter/source reason;
- raw detail when allowed;
- stable top-level reason when raw detail is omitted.

## 9. Adapter Requirements

Adapters translate semantic operations to concrete worlds.

### REQ-ADAPTER-001: Thin adapter

Each adapter SHOULD map semantic patch/query/event contracts onto an existing
world without rebuilding that world.

### REQ-ADAPTER-002: Concrete evidence ownership

The adapter owns seed-specific evidence production. For Onsen, the adapter owns
live viewport pixel evidence. For Nexus, the adapter may own event/causal
evidence.

### REQ-ADAPTER-003: Safe failure

Adapters MUST return `blocked` when an operation is unsafe or disallowed, and
`not_verified` when evidence is unavailable or contradictory.

### REQ-ADAPTER-004: Seed pressure before core extraction

The shared `world-core` SHOULD NOT be extracted from Onsen alone. At least one
non-spatial or causal seed, likely Nexus, SHOULD pressure the schema first.

## 10. Memory And Learning Requirements

Memory and learning are downstream of verification.

### REQ-MEM-001: Recall before weight change

The first adaptation mechanism SHOULD be explicit recall of verified design
history and user preference, not model-weight or reflexive substrate changes.

### REQ-MEM-002: Ingestion is gated

World results MUST NOT enter a verified learning stream until the expression and
verification boundary for that result class has been accepted.

### REQ-MEM-003: Training labels are scoped

If a world result later becomes eligible for #94-style ingestion, the record
MUST state what was verified, what was not verified, and which layer produced
the evidence.

## 11. Non-Goals For v1 Requirements

The requirements do not commit to:

- a full commercial game engine;
- a DCC/editor replacement;
- default-profile LSWR tools;
- automatic #94 ingestion;
- multi-AI concurrent write authority;
- a generic Rust runtime core extracted from Onsen alone;
- GUI automation as the main AI design surface;
- screenshot parsing as primary perception;
- a marketplace or asset pipeline.

## 12. Acceptance Gates

### Gate A: Requirements coherence

The requirements are acceptable when every later task can point to:

- product boundary;
- participant/authority model;
- runtime session loop;
- API boundary;
- human feedback boundary;
- verification ledger;
- non-goals.

### Gate B: Event and feedback schema

The next schema slice is acceptable when it can represent human input,
AI patching, runtime verification, and causal links without requiring Step D.

### Gate C: Nexus pressure

The schema is ready for runtime-core extraction only after it can represent at
least one non-spatial/causal seed without forcing Onsen-specific fields into
the core.

### Gate D: Expression boundary

Presentation or review artifacts are acceptable only when they preserve
lower-layer `verified`, `not_verified`, and `blocked` evidence without
laundering.

### Gate E: Learning boundary

Verified outcome ingestion is acceptable only when the source evidence and human
review semantics are explicitly separated.

## 13. Recommended Next Work

Continue with P2:

```text
docs/design/LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md
```

The P2 document should define concrete event and feedback envelopes, examples,
and acceptance falsifiers.
