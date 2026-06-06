# Live Semantic World Runtime - MVP Shape After Phase 0

**2026-06-06 - role: product/runtime planning**

Parent documents:
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Phase 0 Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_SPEC_2026_06_04.md)
- [Phase 0 Step B Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_B_SPEC_2026_06_05.md)
- [Phase 0 Step C Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_C_SPEC_2026_06_05.md)
- [Landing Plan](LIVE_SEMANTIC_WORLD_RUNTIME_LANDING_PLAN_2026_06_05.md)

Forum anchors:
- `#102`: Phase 0 design, implementation, and Step C final acceptance.
- `#104`: follow-on identity-hardening infrastructure lane, not this runtime lane.

## 0. Purpose

Phase 0 proved that the core interaction loop is feasible. This document turns
that proof into the next product/runtime shape.

It should prevent two common drifts:

1. treating the accepted `world_*` Agent-Bridge tools as the product;
2. treating the project as a generic 3D engine or editor.

The runtime target remains:

> A bidirectional expression medium where humans and AI agents mutate, perceive,
> verify, and discuss one shared semantic world through different interfaces.

## 1. Verified Starting Point

Current accepted facts:

- Onsen is the first spatial/visual seed.
- Phase 0 Step A/B proved render-grounded perception against the human-visible
  onsen viewport.
- Phase 0 Step C exposed the accepted bridge through Agent-Bridge `world_query`,
  `world_patch`, and `world_visibility_query`.
- Step C reached final acceptance only after two hotfixes:
  - `0876bd1`: accept `ONSEN_LSWR_PORT` as a client-side port alias.
  - `5037e01`: lift nested not-verified reasons such as
    `pixel_coverage_zero` into top-level `reason` and
    `verify.evidence.host_reason`, including `include_raw=false`.
- The old `semantic-world-board-patrol` automation is obsolete and stopped.
- The next active board lane, `#104`, is session identity hardening. It improves
  collaboration hygiene but does not define the LSWR product shape.

The proof is not "we built the runtime." It is:

```text
AI patch
  -> live world adapter
  -> human-visible render changes or fails
  -> structured render-grounded perception
  -> honest verified / not_verified / blocked result
```

That is enough to design the MVP.

## 2. MVP Thesis

The MVP is not a game engine. It is also not an editor UI.

The MVP is a **semantic world session** with four properties:

1. **A world can be changed by semantic patches.**
   Agents do not need to click editor controls. They call a stable API.
2. **Humans can experience and influence the same world.**
   Mouse, keyboard, navigation, selections, accept/reject, and comments become
   world-anchored feedback.
3. **The runtime can read back what happened in structured form.**
   It reports state, events, visibility, interaction, verification, and reasons.
4. **Every claim is auditable and reversible.**
   Patches, outcomes, branches, rollbacks, and human feedback carry provenance.

If these four properties hold, the system can later present itself as a 3D tool,
game, companion world, dashboard, simulation, or multi-agent world. If they do
not hold, a richer renderer will only hide the missing contract.

## 3. Minimum Runtime Anatomy

### 3.1 Semantic World Core

The core is an engine-neutral model, not a renderer.

Minimum objects:

| Object | Required in MVP | Purpose |
|---|---|---|
| `World` | yes | Session root, active branch, tick/time, constraints |
| `Entity` | yes | Stable semantic object with components, role, tags, state |
| `Space` | yes | Region, room, path, viewport, or interaction zone |
| `Participant` | yes | Human or AI actor with role, authority, and identity |
| `Patch` | yes | Atomic semantic mutation with reason and expected effect |
| `Event` | yes | Runtime event from patch, human input, render, or adapter |
| `Feedback` | yes | Human or AI response anchored to entities/events |
| `Verification` | yes | Claim result: `verified`, `not_verified`, or `blocked` |
| `Branch` | minimum | Alternative trajectory or rollback group |
| `MemoryLink` | deferred | Link to #94 or AB memory after expression is trusted |

Core rule: the world model must be small enough for agents to reason about, but
structured enough that a human-visible result can be traced back to semantic
objects and decisions.

### 3.2 World Adapter

The adapter maps semantic operations to a concrete running world.

For Onsen:

```text
world.patch(move bath -> cell [x,y])
  -> GameLoopDirector.move_facility(...)
  -> request_render_refresh()
  -> live root viewport perception
  -> verified / not_verified envelope
```

Adapter requirements:

- map semantic IDs to concrete engine objects;
- apply patches or return `blocked` with a machine-readable reason;
- expose render-grounded perception;
- expose human interaction events;
- preserve adapter-specific details without leaking them into core schema;
- never upgrade adapter `verified=false` into success.

### 3.3 Agent Surface

The agent surface is the stable API an AI can use directly.

Minimum calls:

```text
world.query(selector?) -> WorldSnapshot
world.patch(patch) -> PatchResult
world.visibility.query(query) -> VisibilityReport
world.events.query(cursor?, filter?) -> EventPage
world.feedback.query(cursor?, filter?) -> FeedbackPage
world.branch.create(reason, base?) -> BranchRef
world.rollback(target) -> RollbackResult
```

The existing Step C `world_*` tools cover only the first three calls. They are a
bridge surface for the Onsen seed, not the whole agent surface.

### 3.4 Human Surface

The human surface is not necessarily an editor. It is the human-facing way to
experience, direct, and judge the world.

MVP surface:

- live world viewport;
- mouse and keyboard interaction;
- selection or focus target;
- accept/reject/comparison controls;
- optional short text feedback;
- branch/rollback review;
- visible verification status when the AI claims a result.

The human should not need to understand the internal schema. The runtime should
translate human behavior into world-anchored events and feedback.

### 3.5 Feedback Bus

The feedback bus converts human and AI activity into structured records.

Minimum event types:

```text
human.move_path
human.click
human.hover_or_dwell
human.select
human.reject
human.accept
human.note
ai.patch_proposed
ai.patch_applied
runtime.visibility_measured
runtime.verification_result
runtime.branch_created
runtime.rollback_applied
```

Each event should carry:

- participant;
- timestamp or tick;
- branch;
- entity refs where available;
- viewport/camera refs where relevant;
- cause event or patch where relevant;
- confidence / verification status where relevant.

### 3.6 Verification Ledger

The verification ledger is the trust layer between agents and humans.

Every claim that may affect design or memory should become one of:

| Verdict | Meaning |
|---|---|
| `verified` | Evidence confirms the claim in the relevant world/render context |
| `not_verified` | Evidence contradicts the claim or cannot confirm it |
| `blocked` | The runtime could not safely attempt the operation |

Evidence should preserve:

- method;
- measured values;
- source render or event stream;
- host/adapter reason;
- raw detail when allowed;
- stable top-level reason even when raw detail is omitted.

This is the Phase 0 lesson: reasonless failure is not enough. The AI must know
why the world did not verify.

## 4. MVP Session Loop

The first product-like session should look like this:

```text
1. Human opens a live world session.
2. AI reads world.query and recent events.
3. Human gives a goal or interacts naturally.
4. AI proposes one semantic patch with an expected effect.
5. Runtime applies the patch through the adapter.
6. Human-visible render changes.
7. Runtime emits structured visibility and event feedback.
8. Verification ledger records verified / not_verified / blocked.
9. Human accepts, rejects, annotates, or continues playing.
10. AI revises, rolls back, branches, or presents the result.
```

The MVP succeeds when this loop can run repeatedly without screenshots as the
AI's primary perception channel.

## 5. Product Surfaces

### 5.1 World View

Primary viewport for human experience.

Requirements:

- show the current branch;
- expose selection/focus if available;
- reveal enough verification state to avoid false confidence;
- avoid developer-only clutter during normal play.

### 5.2 Agent Inspector

Structured readback panel for agents and technical reviewers.

Requirements:

- world snapshot;
- recent patches;
- recent events;
- visibility report;
- verification ledger;
- adapter status;
- branch state.

This can be terminal/API-first in early MVP. It does not need to be a polished UI.

### 5.3 Review / Branch Panel

Human-friendly comparison and rollback surface.

Requirements:

- before/after patch summary;
- expected effect and measured result;
- accept/reject;
- rollback target;
- branch label;
- concise reason for failure or blocked state.

This panel is the natural bridge to `present()` and #92.

## 6. Relationship To #92 And #94

Step D should be expression first, learning second.

Recommended order:

1. **#92 present compatibility.**
   Present verified and not-verified world results to humans without changing
   their meaning.
2. **Human review loop.**
   Let humans accept, reject, compare, and annotate those results.
3. **#94 verified-outcome ingestion.**
   Only after the expression boundary is trusted, feed accepted verified outcomes
   into memory/training streams.

Do not ingest a world result into #94 just because a patch ran. It must survive
the verification ledger and expression boundary.

## 7. Phase 1 Direction

Phase 1 should not immediately extract a generic Rust runtime from Onsen alone.

Recommended sequence:

### P1.1 Step D Spec

Write a design-only Step D spec over the accepted Step C surface:

- map `world_*` results into `present()` compatible packets;
- preserve `verified_to`, `verify.method`, and top-level reason;
- show `not_verified` honestly;
- do not write #94 memory yet;
- define acceptance gates for expression correctness.

### P1.2 MVP Session Shell

Build a small session shell around the Onsen seed:

- human viewport;
- agent calls through `world_*`;
- event/feedback capture;
- branch/rollback placeholder;
- review/present packet generation.

This is where the runtime starts feeling like a product.

### P1.3 Second Seed Pressure

Add Nexus or another non-spatial/causal seed before extracting the core schema.

Reason:

- Onsen pressures spatial visibility and human-readable render.
- Nexus pressures event causality, replay, branch history, and multi-view state.
- A schema that survives both is more likely to be a runtime core, not an Onsen
  adapter dressed as a core.

### P1.4 Rust Runtime Core Extraction

Only after P1.2 and P1.3, extract a Rust core for:

- schema types;
- patch log;
- event stream;
- verification ledger;
- branch/rollback;
- authority rules;
- adapter traits.

Rust is the right long-term substrate for determinism, performance, and typed
contracts. It should not be used to prematurely freeze an under-pressured schema.

## 8. Acceptance Gates For MVP

### M1. Same-render grounding

Any visual claim must be derived from the render surface the human could see.

### M2. Bidirectional world anchoring

Human interactions and AI patches must both reference the same semantic world
objects where possible.

### M3. Honest failure

Unavailable host, inert render, occluded entity, invalid patch, and unmeasurable
expected effect must return machine-readable failure or `not_verified` reasons.

### M4. Reversible patches

Every applied patch belongs to a rollback group or branch.

### M5. Expression fidelity

`present()` and human-facing review surfaces must not change a lower layer's
verification meaning.

### M6. Cross-seed pressure

The first extracted core schema must be validated against one spatial/visual seed
and one event/causal seed.

## 9. Non-goals For The Next Slice

Do not build these yet:

- a full 3D editor;
- asset generation pipeline;
- public multiplayer;
- multi-agent authority;
- marketplace/export workflow;
- generic physics simulation;
- #94 ingestion before Step D expression is trusted;
- Rust core extraction before second-seed pressure.

These may become valid later. They are too early for the next slice.

## 10. Concrete Next Action

The next LSWR product action should be:

> Draft and accept a Step D expression spec that maps accepted Step C world
> results into human-visible `present()` packets, while preserving verification
> semantics and deferring #94 ingestion.

This is the smallest step that advances the original human-AI interaction thesis
without reopening Step C implementation or drifting into identity-hardening.

After Step D spec acceptance, the next implementation slice should be the MVP
session shell, not more abstract runtime-core design.
