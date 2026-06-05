# Live Semantic World Runtime v0

> Status: DRAFT / DESIGN REQUIREMENTS, 2026-06-04.
>
> Amended 2026-06-04: §4 and §10 tightened, and §15 (Phase 0 — Controlling
> Interpretation) added, per peer review (forum #102 posts #2375/#2378, accepted in
> #2380). Full rationale: LIVE_SEMANTIC_WORLD_RUNTIME_V0_REVIEW_2026_06_04.md.
>
> Working name: Live Semantic World Runtime.
>
> Chinese working name: 实时语义世界运行时.
>
> Provenance: owner + Codex design discussion on agent-native 3D/creative
> runtime, narrowed from open-source game-engine research into a human-AI-AI
> interaction layer built on one shared semantic world model.

## 1. Thesis

This project is not first a 3D engine, an editor, or a game.

It is a **bidirectional expression medium over a shared semantic world model**:

- humans experience, interact, direct, reject, annotate, and influence;
- AI agents generate, edit, explain, simulate, test, and negotiate;
- the runtime keeps both sides grounded in the same world state, event stream,
  design history, and reversible semantic changes.

3D is the first concrete presentation layer because it gives immediate spatial,
visual, and interactive feedback. It is not the product boundary. The same
semantic interaction shape should eventually support games, companion worlds,
knowledge spaces, dashboards, music-video worlds, education simulations, and
other live creative environments.

One-line definition:

> A live world where humans and AI agents interact through different expression
> forms while mutating and perceiving one unified semantic state.

## 2. Problem

Current creative tools are optimized for human GUI manipulation or for AI code
generation, but not for a continuous human-AI creative loop.

Common failure modes:

- AI can generate files but cannot reliably perceive the design result except
  through screenshots or brittle GUI control.
- Humans can interact with visual output but their feedback often becomes
  unstructured text, disconnected from the scene objects and design decisions.
- Traditional editors expose pixels, widgets, and parameters rather than a
  unified model of intent, constraints, objects, behavior, feedback, and history.
- A generated scene may be visible to humans but opaque to agents; a structured
  agent patch may be precise but emotionally or spatially unreadable to humans.

The desired system makes the world itself queryable, editable, perceivable,
auditable, branchable, and playable.

## 3. Product Boundary

### 3.1 What It Is

An agent-native runtime with:

- a shared semantic world model;
- a live visual/interactive client for humans;
- a design API for AI agents;
- structured state, event, feedback, and visibility streams;
- semantic patching, branching, rollback, and memory;
- optional export to standard artifacts such as GLB/glTF once the world state
  needs to leave the runtime.

### 3.2 What It Is Not

For v0, this is not:

- a full commercial game engine;
- a traditional DCC editor replacement;
- a large MMO platform;
- a general AGI world simulator;
- a physics-heavy simulation engine;
- a marketplace or asset pipeline product;
- a GUI-first editor where AI drives mouse clicks.

The first milestone should validate the interaction shape before optimizing for
engine completeness.

## 4. Core Interaction Model

The runtime should support this loop:

```text
AI proposes or applies semantic patch
  -> runtime updates world state
  -> human sees/plays the changed world
  -> runtime captures interaction and semantic feedback
  -> AI reads state/events/feedback
  -> AI revises, branches, explains, or rolls back
```

The key distinction: AI perception should not depend primarily on screenshots.
Screenshots remain useful for audits and aesthetic calibration, but the primary
feedback channel should be structured world data.

Example visibility feedback:

```json
{
  "camera": "player_main",
  "visible_entities": [
    {
      "id": "entrance_gate",
      "screen_area": 0.18,
      "occluded": false,
      "semantic_role": "arrival_landmark"
    },
    {
      "id": "welcome_sign",
      "screen_area": 0.02,
      "occluded": true,
      "semantic_role": "wayfinding_hint"
    }
  ],
  "warnings": [
    "welcome_sign_visible_but_too_small",
    "guide_npc_overlaps_arrival_landmark"
  ]
}
```

Example agent patch:

```json
{
  "op": "set_transform",
  "entity": "bathhouse.roof",
  "position": [0.0, 4.2, -1.5],
  "reason": "improve silhouette from entry camera",
  "expected_effect": ["stronger_arrival_identity", "less_visual_overlap"],
  "rollback_group": "arrival_readability_pass_01"
}
```

> Refinement (review #2375, accepted #2380): `expected_effect` should move from
> prose tags toward **measurable falsifier clauses** wherever possible, with
> `not_verified` as a first-class result. The example's `"stronger_arrival_identity"`
> becomes a checkable claim such as `arrival_landmark.screen_area: 0.18 -> >= 0.25`
> and `welcome_sign.occluded: true -> false`, evaluated against the human-visible
> render. An effect that cannot be evaluated returns `not_verified` rather than
> silently counting as success. This closes the loop in this section and produces
> the verified-labeled records the §14 / #94 training stream consumes.

## 5. User Roles

The system should not force one human role. The same person may shift between:

- **player**: experiences and navigates the world;
- **collaborator**: gives natural-language direction and preferences;
- **director**: constrains goals, style, priorities, and boundaries;
- **reviewer**: accepts, rejects, compares, or annotates outcomes;
- **influence source**: affects the world through behavior even without explicit
  editing.

AI agents may shift between:

- **creator**: generates objects, spaces, behaviors, and presentation;
- **editor**: applies local revisions and cleanup;
- **observer**: reads state, events, visibility, and feedback;
- **simulator**: runs scenarios and predicts outcomes;
- **critic**: evaluates readability, intent fit, novelty, and constraints;
- **negotiator**: coordinates with other agents or humans.

The long-term design should support one-to-one, one-to-many, many-to-one, and
many-to-many interaction, including AI-AI interaction inside the same world.

## 6. Shared Semantic Model

The first model should stay small but expressive. v0 should prioritize:

| Object | Purpose |
|---|---|
| `World` | Root state, time, branches, active constraints |
| `Entity` | Named object with components, tags, role, and state |
| `Space` | Region, room, zone, path, or viewpoint cluster |
| `Agent` | AI participant with capabilities, intent, and authority |
| `Human` | Human participant with interaction history and preferences |
| `Intent` | Goal, direction, style request, or desired outcome |
| `Feedback` | Explicit or inferred response from human/agent/runtime |
| `Constraint` | Budget, style, safety, performance, lore, or design boundary |
| `Patch` | Atomic semantic mutation with reason and expected effect |
| `Branch` | Alternative world trajectory with comparable outcomes |
| `Memory` | Durable design learning and preference history |

The model should represent more than visual shape. A world object may include:

- visual form;
- audio behavior;
- text/narrative role;
- interaction affordance;
- emotional tone;
- gameplay function;
- social meaning;
- performance budget;
- relationship to other entities.

## 7. Feedback Channels

v0 should prioritize mouse and keyboard interactions:

- movement path;
- click target;
- hover/dwell;
- selection;
- repeated attempt;
- failed interaction;
- undo/redo request;
- branch choice;
- accept/reject;
- typed note or short natural-language feedback.

Later channels:

- voice;
- gesture;
- gaze/attention;
- biometric or comfort signals;
- richer collaborative annotation;
- external tool or game-controller input.

All feedback should be anchored when possible:

```json
{
  "type": "human_feedback",
  "target": "entrance_area",
  "signal": "too_crowded",
  "source": "explicit_text",
  "raw": "这里太挤了，入口不像温泉旅馆",
  "normalized": {
    "issue": "visual_density_too_high",
    "desired_direction": "more_breathing_room",
    "semantic_axes": ["cultural_affordance", "silhouette", "emotional_tone"]
  }
}
```

## 8. AI Authority

The AI side should have high autonomy, but authority must be explicit and
bounded by interaction mode.

Recommended modes:

| Mode | AI Authority | Human Experience |
|---|---|---|
| `observe` | Read-only | Human plays/interacts; AI learns |
| `suggest` | Propose patches | Human compares/accepts/rejects |
| `coedit` | Apply reversible patches | Human sees live changes and can undo |
| `autonomous` | Apply patches continuously | Human experiences an evolving world |
| `locked` | No mutation | Stable review/export/play session |

All mutating modes require:

- patch reason;
- affected entities;
- expected effect;
- rollback group;
- before/after state diff;
- feedback linkage after the change.

## 9. Runtime Requirements

### 9.1 Minimum v0 Runtime

The first runtime should provide:

- load/save semantic world state;
- render an interactive visual scene;
- accept mouse/keyboard input;
- stream structured events;
- apply semantic patches live;
- query world/entity/space state;
- query visibility and interaction focus;
- maintain change history;
- support branch and rollback;
- export a snapshot for review.

### 9.2 Agent API

Minimum commands:

```text
world.get
world.query
world.patch
world.branch.create
world.branch.compare
world.rollback
world.events.subscribe
world.feedback.list
world.visibility.query
world.snapshot.export
```

### 9.3 Human Client

The first client should be a simple live viewer, not a full editor.

Required:

- visible scene/world;
- mouse and keyboard navigation;
- basic object interaction;
- branch compare/select;
- accept/reject controls;
- text feedback;
- visible change markers when AI edits the world;
- undo/revert affordance for human trust.

## 10. Perception Without Screenshot Dependence

The runtime should provide structured perception:

- entity visibility from active cameras;
- screen area and occlusion;
- object-id/depth/normal buffers where useful;
- focus/selection/current interaction target;
- navigation path and stuck points;
- collisions and trigger events;
- UI/affordance state;
- frame timing and performance;
- semantic warnings from validators.

Screenshots are still useful as:

- audit evidence;
- visual regression checks;
- aesthetic spot checks;
- human-visible artifacts for review.

But screenshots should not be the main AI perception substrate.

Two hard requirements (review #2375/#2378, accepted #2380), because structured
perception can otherwise report "all green" on a world that is inert to the human —
observed live in onsen-hd, where smoke was green and golden bytes were unchanged
while the player saw a frozen world for four rounds:

- **Render-grounded:** every visibility/perception value must be derived from the
  same render pipeline the human actually sees — never a proxy (headless smoke,
  golden bytes, or logical state). Perception bound to a parallel proxy is exactly
  how the human view and the AI view silently diverge.
- **No green-but-inert:** every perception assertion and every patch
  `expected_effect` must carry a falsifier that can return `not_verified`, and a
  change that is invisible to the human must never report as a human-visible
  success.

## 11. Technical Direction

Do not require Rust in phase 0 if it slows the first interaction proof.

Recommended evaluation posture:

- pick the fastest stack for a real closed loop first;
- keep the semantic model and API portable;
- treat Rust as the long-term performance/core-runtime candidate;
- avoid coupling the concept to any one renderer, UI framework, or game engine.

Possible long-term Rust stack:

```text
world-core       # semantic model / ECS or scene graph / state diffs
design-api       # patch, query, branch, rollback, inspect
runtime          # simulation, input, scripting, event loop
renderer         # wgpu or Bevy-based visual layer
human-client     # web/native interactive viewer
telemetry-bus    # human actions, visibility, state diffs, feedback
exporter         # glb/gltf/usd/scene snapshots
memory-layer     # preferences, history, reusable design lessons
```

## 12. MVP Proposal

Build a single-human, single-AI live scene prototype:

1. A small semantic world with entities, spaces, roles, constraints, and patches.
2. A visual client where the human can navigate with mouse/keyboard.
3. An agent API that can add, remove, move, restyle, and annotate entities.
4. Structured event feedback for movement, clicks, dwell, selection, accept,
   reject, and text comments.
5. Visibility/readability metrics for the current camera.
6. Branch/rollback for AI-generated alternatives.
7. A session log that explains what changed and why.

Acceptance:

- AI can change the world without GUI control.
- Human can experience the change immediately.
- Human feedback is anchored to semantic objects where possible.
- AI can read structured world, feedback, and visibility state.
- A rejected change can be rolled back.
- A preferred branch can be preserved as durable world history.

## 13. Open Questions

1. Which first presentation stack gives the fastest loop: web, Bevy, Godot,
   custom Rust/wgpu, or another hybrid?
2. What is the smallest compelling world seed: room, bathhouse entrance,
   companion habitat, abstract knowledge space, or game-like playground?
3. How much autonomous live mutation feels useful rather than disorienting?
4. Which feedback signals become reliable enough to update long-term human
   preference memory?
5. How should multiple AI agents negotiate authority over the same world?
6. What export target matters first: GLB, web app, playable prototype, design
   trace, or Agent-Bridge memory substrate?

## 14. Relation To Agent-Bridge

Agent-Bridge is a natural substrate for the non-rendering half:

- memory for durable design preferences and failed/successful attempts;
- forum/board for design decisions, branches, and coordination;
- presence/avatar surfaces for live participant state;
- event spine and telemetry for replayable interaction history;
- work memory for active session scratchpad;
- future task/state-machine surfaces for multi-agent world work.

This design should remain a concept/RFC until a small prototype proves the
interaction loop. Do not route it as an immediate core Agent-Bridge runtime
change without an explicit owner decision.

## 15. Phase 0 — Controlling Interpretation

Per peer review (forum #102 posts #2375/#2378, accepted by Codex in #2380), the
following is the controlling interpretation of phase 0. §1–§14 above remain the
broader product vision; this section governs what phase 0 actually builds. Full
rationale and evidence: `LIVE_SEMANTIC_WORLD_RUNTIME_V0_REVIEW_2026_06_04.md`.

1. **Extract, do not build greenfield.** Of the §11 stack, four boxes already exist
   live: renderer + human-client (onsen-hd / nexus-civilization), memory-layer
   (Agent-Bridge memory), and telemetry-bus (AB event_spine + nexus's hash-chained
   event log + causal DAG). Phase 0 builds only the two missing boxes — `world-core`
   (the §6 portable schema) and `design-api` (§9.2) — as thin contracts wired to the
   existing worlds. `design-api` is itself half-present: the patch half is onsen's
   `director.move/rotate/flip_facility` (live runtime mutation, not file-edit +
   restart); the events half is nexus's EventStore. The genuinely-new surfaces are
   `world.visibility.query` and branch/rollback UX.
2. **Onsen-hd is the first seed; nexus-civilization is the second.** onsen is the
   spatial/visual/readability axis (has live patching, lacks perception — so it is
   the best testbed for `visibility.query`). nexus is the systemic/temporal/causal
   axis (event-sourcing + causal DAG + replay), proving the schema is not
   spatial-only and donating the Branch/event machinery. `world-core` is extracted
   over onsen ∩ nexus (one adapter per world); neither game is rebuilt.
3. **No biocortex-rs in phase 0.** AB memory (episodic recall) + the #94
   verified-outcome flow are sufficient; the AI adapts to the new interaction form
   by in-context recall, not weight change. Reserve biocortex-rs for an
   implicit/high-frequency reflexive residual, and only after that residual is
   measured — run it shadow-gated (the AiOT Seed L2 substrate was correctly
   falsified this way before it could pollute retrieval).
4. **No multi-AI mutable-world authority in phase 0.** Unify the semantic layer
   first. Concurrent multi-writer authority over one mutable world needs per-region
   single-writer leases or CRDT-style mergeable patches (optimistic read-then-write
   is invalid under concurrency); this stays v1.
5. **Cheapest first proof.** Expose onsen's existing patch API plus a new
   `world.visibility.query` as an MCP surface, and close the §4 loop against a world
   a human is already playing — without screenshots. If it closes, the general
   runtime is justified; if it cannot close on onsen (already ~60% built), a
   greenfield runtime would not either. Capture verified outcomes through #94 only
   after a real closed loop is observed.

