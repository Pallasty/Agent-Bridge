# Live Semantic World Runtime - Engine/API Research Refresh

**2026-06-06 - role: P6 engine/API refresh**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Nexus seed pressure](LIVE_SEMANTIC_WORLD_RUNTIME_NEXUS_SEED_PRESSURE_2026_06_06.md)
- [Core extraction criteria](LIVE_SEMANTIC_WORLD_RUNTIME_CORE_EXTRACTION_CRITERIA_2026_06_06.md)

Forum anchors:
- `#105` post `#2556`: P6 start notice.

## 0. Status

This document is docs-only. It does not modify `crates/bridge`, resume Step D,
register MCP tools, or open #92/#94 wiring.

It refreshes the original open-source engine research using the P5 rule:

> Engines are adapters or runtime hosts. They are not LSWR core.

## 1. Source Refresh

Official or primary sources checked on 2026-06-06:

| Stack | Source anchors |
|---|---|
| Bevy | `https://docs.rs/bevy/latest/bevy/scene/`, `https://docs.rs/bevy/latest/bevy/reflect/` |
| Fyrox | `https://fyrox.rs/`, `https://fyrox-book.github.io/scene/graph.html`, `https://fyrox-book.github.io/scripting/script.html` |
| Godot | `https://docs.godotengine.org/en/stable/getting_started/step_by_step/nodes_and_scenes.html`, `https://docs.godotengine.org/en/stable/classes/class_scenetree.html`, `https://docs.godotengine.org/en/stable/tutorials/plugins/editor/index.html`, `https://docs.godotengine.org/en/4.6/classes/class_editordebuggerplugin.html`, `https://docs.godotengine.org/en/4.2/classes/class_packedscene.html` |
| Three.js/Web | `https://threejs.org/docs/pages/Object3D.html`, `https://threejs.org/docs/pages/WebGLRenderer.html` |
| Custom Rust pieces | `https://wgpu.rs/`, `https://rapier.rs/docs/`, `https://docs.rs/gltf/latest/gltf/`, `https://docs.rs/egui/latest/egui/` |

No Reddit/forum claims were used as decision evidence.

## 2. Evaluation Criteria

P6 scores engines as LSWR adapters against these questions:

| Criterion | Meaning |
|---|---|
| structured state | Can an agent query stable world objects without screenshots? |
| editable API | Can an agent mutate the world through code/API? |
| readback | Can the agent read the resulting state/evidence back? |
| human surface | Can humans interact with the same world naturally? |
| event/evidence bus | Can it emit events, verification, and failure reasons? |
| rollback/replay | Can changes be branched, reverted, or replayed? |
| Rust fit | Does it preserve a Rust-first implementation path? |
| adapter complexity | How much custom LSWR glue is needed? |

Scoring:

```text
3 = strong native fit
2 = feasible with moderate adapter work
1 = possible but requires heavy custom glue
0 = not a fit for this criterion
```

## 3. Candidate Matrix

| Stack | Structured state | Editable API | Readback | Human surface | Event/evidence bus | Rollback/replay | Rust fit | Adapter complexity | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Godot | 3 | 3 | 2 | 3 | 2 | 2 | 1 | 2 | Best mature visual/editor adapter |
| Fyrox | 3 | 3 | 3 | 2 | 2 | 2 | 3 | 2 | Best Rust-first engine/editor adapter |
| Bevy | 3 | 3 | 3 | 1 | 2 | 2 | 3 | 2 | Best Rust ECS/runtime adapter |
| Three.js/Web | 2 | 3 | 3 | 3 | 2 | 2 | 1 | 1 | Fastest readable surface prototype |
| Custom Rust runtime | 3 | 3 | 3 | 1 | 3 | 3 | 3 | 3 | Best eventual LSWR core host after schema |

The matrix does not select one winner. It separates adapter roles.

## 4. Stack Notes

### 4.1 Godot

Godot is the strongest mature visual/editor adapter candidate.

Source facts:

- Godot games are scene trees; each scene is a tree of nodes.
- Nodes have names, editable properties, callbacks, and child relationships.
- `SceneTree` manages node hierarchy, groups, scene switching, and group method
  or property calls.
- Editor plugins and debugger plugins provide extension and debugger surfaces.
- `PackedScene` can pack owned nodes into a saved scene resource.

LSWR fit:

- Strong human surface and editor ergonomics.
- Good semantic object model through nodes, scenes, groups, resources, and
  serialized scene files.
- Good for Onsen-style spatial/visual proof.
- Requires a custom adapter for stable verification envelopes, event history,
  rollback groups, and evidence queries.

Risk:

- Rust is not the primary scripting path unless using GDExtension or an external
  bridge.
- Editor/debugger automation should not become LSWR core. It remains adapter
  plumbing.

Recommended use:

- Use Godot when the priority is a rich human-facing visual world.
- Keep LSWR truth outside Godot editor state, then project into Godot.

### 4.2 Fyrox

Fyrox is the strongest Rust-first engine/editor adapter candidate.

Source facts:

- Fyrox is a Rust 2D/3D game engine with a scene editor.
- Its graph is the central scene-object structure with hierarchical
  relationships.
- Scripts are Rust containers assigned to scene nodes.
- `Visit` handles serialization/deserialization for editor scene files.
- `Reflect` supports field iteration and editor-style inspection.

LSWR fit:

- Strong Rust fit with a scene graph and editor.
- Strong readback potential through Rust data, graph traversal, reflection, and
  serialization.
- More native to Rust than Godot while still offering editor tooling.

Risk:

- LSWR still needs a custom event/evidence/feedback ledger.
- Human/editor surface maturity should be validated with a small real scene
  before choosing it as the main visual adapter.

Recommended use:

- Use Fyrox for a Rust-first visual runtime prototype when editor integration is
  needed and custom LSWR glue is acceptable.

### 4.3 Bevy

Bevy is the strongest Rust ECS/runtime adapter candidate.

Source facts:

- Bevy scene support provides scene definition, instantiation, and
  serialization/deserialization.
- Scenes are collections of entities and components.
- `DynamicScene` can be built from a `World`, written back to a `World`, and
  serialized into Bevy's scene format.
- Bevy reflection can dynamically interact with Rust values, access runtime type
  metadata, and serialize/deserialize data.

LSWR fit:

- Very strong match for agent-readable structured state.
- Strong match for a Rust data model, actions, query systems, and verification
  events.
- Good basis for a headless or semi-headless semantic runtime.

Risk:

- This source refresh confirms strong code/runtime introspection, not a mature
  first-party human editor equivalent to Godot's scene editor.
- A human-facing authoring/review surface must be built or paired with another
  surface.

Recommended use:

- Use Bevy as a Rust runtime adapter, not the first human editor target.
- Pair it with a web or custom review surface for LSWR human feedback.

### 4.4 Three.js / Web Stack

Three.js is the fastest readable surface prototype.

Source facts:

- `Object3D` is the base class for most 3D objects.
- Objects can be added, removed, found by ID/name/property, traversed, raycast,
  transformed, and serialized with `toJSON()`.
- Object add/remove events and render callbacks are available.
- WebGLRenderer and WebGPURenderer surfaces can be inspected and tested through
  browser tooling.

LSWR fit:

- Excellent for fast agent-driven scene generation and readback.
- Browser events map naturally to human input events.
- JSON scene readback is direct and cheap.
- Good for present/review surfaces and minimal 3D prototypes.

Risk:

- Not a full game engine by itself.
- Rust fit is indirect unless paired with WASM/Rust backend.
- Needs custom world state, event ledger, physics, persistence, and rollback.

Recommended use:

- Use Three.js/Web for the smallest human-interactive LSWR prototype.
- Treat it as a surface adapter over a semantic state store, not as the core.

### 4.5 Custom Rust Runtime

A custom Rust runtime is the cleanest long-term LSWR host, but not the next
editing surface.

Source facts:

- `wgpu` is a safe, portable Rust graphics library based on WebGPU.
- Rapier provides Rust 2D/3D physics with contact events, scene queries,
  snapshotting, and optional cross-platform determinism.
- The Rust `gltf` crate supports loading glTF 2.0 assets.
- `egui` provides immediate-mode GUI in pure Rust.

LSWR fit:

- Best control over events, verification, replay, rollback, and evidence.
- Best path for performance and deterministic host design.
- Best eventual place for `world-core` once schema and adapter contracts are
  accepted.

Risk:

- Highest build cost.
- Weakest immediate human editor unless paired with a custom UI or web/Godot
  surface.
- Premature if the core schema is not accepted.

Recommended use:

- Do not start here for visual authoring.
- Start here only after `world-core` schema and evidence contracts are stable.

## 5. Role-Based Recommendation

| Need | Recommended stack |
|---|---|
| Fastest AI-generated interactive 3D scene | Three.js/Web |
| Mature human visual editing | Godot |
| Rust-first editor-backed engine | Fyrox |
| Rust-first semantic ECS runtime | Bevy |
| Long-term deterministic LSWR runtime | Custom Rust core with wgpu/Rapier/gltf/egui as optional pieces |

This means the LSWR roadmap should not choose "the engine". It should choose
adapter roles.

## 6. Minimal Next Prototype

The next prototype should be a web-first semantic scene adapter:

```text
semantic world JSON
  -> Three.js scene projection
  -> browser human interaction events
  -> structured event/evidence log
  -> agent reads world/evidence, not screenshots
```

Why this first:

- lowest setup cost;
- easiest live human interaction;
- easiest JSON readback;
- easiest browser-based event capture;
- keeps engine choice reversible;
- can later be replaced by Bevy, Fyrox, or Godot adapters.

Minimum components:

| Component | Requirement |
|---|---|
| semantic state store | stable `World`, `Entity`, `Action`, `Event`, `Verification` JSON |
| projector | deterministic state-to-Three.js scene projection |
| mutation API | apply semantic actions, not imperative DOM/editor commands |
| readback API | export semantic state, scene JSON, events, evidence |
| human input adapter | click/select/hover/note/accept/reject events |
| evidence adapter | render presence, hit-test, object bounds, event presence |
| rollback | action log plus previous-state snapshot |

This prototype would directly test the original idea without committing to a
heavy engine or Rust core too early.

## 7. Rust Path

Rust should enter in this order:

1. Shared schema types after P5/P6 acceptance.
2. Event/evidence ledger.
3. Optional Bevy/Fyrox adapter experiment.
4. Deterministic simulation or physics where needed.
5. Rendering/runtime host only after the adapter contract is proven.

Using Rust for performance is still right. Using Rust before the interaction
contract is stable would slow the research loop.

## 8. P7 Recommendation

The next package should define a tiny LSWR web prototype spec:

- one semantic scene JSON shape;
- three agent actions;
- three human input events;
- three verification cases;
- one rollback path;
- one explicit "not verified" visual state;
- no screenshot perception requirement.

This would turn the research back into a runnable artifact without restarting
the halted Step D line.
