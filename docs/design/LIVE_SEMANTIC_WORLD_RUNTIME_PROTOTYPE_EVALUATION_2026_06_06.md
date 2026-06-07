# Live Semantic World Runtime - Prototype Evaluation And P10 Decision

**2026-06-06 - role: P9 prototype evaluation / next implementation choice**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Human input mapping](LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md)
- [Nexus seed pressure](LIVE_SEMANTIC_WORLD_RUNTIME_NEXUS_SEED_PRESSURE_2026_06_06.md)
- [Core extraction criteria](LIVE_SEMANTIC_WORLD_RUNTIME_CORE_EXTRACTION_CRITERIA_2026_06_06.md)
- [Engine/API research refresh](LIVE_SEMANTIC_WORLD_RUNTIME_ENGINE_API_REFRESH_2026_06_06.md)
- [Tiny web prototype spec](LIVE_SEMANTIC_WORLD_RUNTIME_WEB_PROTOTYPE_SPEC_2026_06_06.md)

Prototype:
- `prototypes/lswr-web-prototype/`
- branch `codex/lswr-web-prototype-implementation`
- commit `b49f471`

Forum anchors:
- `#105` post `#2562`: P8 implementation DONE.
- `#105` post `#2563`: P9 START.

## 0. Status

This is a decision artifact. It does not modify runtime crates, register MCP
tools, resume Step D, merge `lswr_present.rs`, or open #92/#94.

P8 proved a working browser interaction loop. P9 decides what should be
implemented next.

## 1. Current Verified State

P8 is an in-memory Vite + Three.js prototype with semantic readback.

Latest verification rerun during P9:

```text
npm run verify:browser
```

Result:

| Gate | Result |
|---|---|
| `WEB-001` add entity + readback | passed |
| `WEB-002` move entity + position evidence | passed |
| `WEB-003` human select event | passed |
| `WEB-004` human reject does not rewrite verification | passed |
| `WEB-005` forced projection miss -> `not_verified` | passed |
| `WEB-006` blocked action leaves semantic state unchanged | passed |
| `WEB-007` rollback restores prior semantic state | passed |
| `WEB-008` structured readback sufficient without screenshot semantics | passed |

Browser evidence:

| Surface | Evidence |
|---|---|
| Desktop canvas | `brightPixels=198756`, `colorBuckets=68`, `939x860` |
| Mobile canvas | `brightPixels=45801`, `colorBuckets=68`, `390x479` |
| Mobile layout | `scrollWidth=390`, `viewportWidth=390`, `sceneHeight=479` |
| Latest rollback | `verdict=verified`, `method=web_scene_rollback_check`, `semantic_state_restored=true` |

Screenshots remain audit evidence only. The pass condition is structured
readback through `window.lswr.world_export()`.

## 2. What P8 Proved

### 2.1 Shared semantic state can drive a live surface

The browser scene uses semantic JSON as the source of truth and Three.js as a
projection adapter. This satisfies the original thesis that the visible world is
an expression surface over a shared semantic form, not the core itself.

### 2.2 Agent readback does not need screenshot semantics

The agent-facing readback contains:

- `world`;
- `entities`;
- `events`;
- `verification`;
- `rollback`;
- `projection.projected_entities`;
- `projection.unprojected_entities`.

The canvas screenshot is useful for nonblank and layout checks, but the agent
does not need to infer object state from pixels.

### 2.3 Human input can feed the same semantic history

The prototype records human selection, drag movement, and accept/reject
decisions as events. A human reject is a decision event and does not rewrite the
lower-layer verification record.

This matches P2/P3's central rule: raw human behavior and interpreted feedback
must be separable.

### 2.4 Verification needs to stay independent from presentation

P8 demonstrates all three verdicts:

| Verdict | P8 path |
|---|---|
| `verified` | add/move/material projected with evidence |
| `not_verified` | semantic add succeeds but projection is intentionally absent |
| `blocked` | locked platform move is rejected before mutation |

The `not_verified` path shows an explicit unconfirmed marker. It does not
display success wording.

### 2.5 Rollback is a core behavior, not an editor affordance

The prototype stores action-log rollback groups, restores prior semantic state,
emits `runtime.rollback_applied`, and verifies the restored projection.

This makes rollback a runtime contract rather than a UI-only undo button.

## 3. What P8 Did Not Prove

P8 deliberately did not prove:

- durable storage;
- replay across browser reloads;
- schema portability into Rust;
- compatibility with the Nexus event/causal seed in executable code;
- adapter independence beyond a single Three.js surface;
- multi-participant sync;
- MCP tool safety;
- #92 present wiring;
- #94 verified-outcome ingestion.

It also keeps schema, ledger, projection, and UI in one browser app. That is
acceptable for P8, but it is the main pressure point for P10.

## 4. Candidate Next Paths

### 4.1 Expand the Web UI

Benefits:

- immediate visible progress;
- more human interaction cases;
- better demonstration value.

Problem:

- it deepens a single-adapter prototype before the reusable core is extracted;
- it risks turning LSWR into a web editor project.

Decision: defer.

### 4.2 Add a Second Visual Adapter

Candidates: Godot, Fyrox, Bevy, or a second Three.js scene type.

Benefits:

- catches adapter assumptions;
- aligns with P5's anti-single-seed extraction rule.

Problem:

- without shared Rust schema and ledger, each adapter will invent its own event
  and verification shape;
- this repeats the P8 mixing problem in another surface.

Decision: defer until P10 creates a core skeleton.

### 4.3 Harden the JavaScript Event/Evidence Ledger

Benefits:

- closest to the P8 code;
- fast iteration;
- can improve browser tests quickly.

Problem:

- the user has already identified Rust as the likely performance and substrate
  path;
- a deeper JS ledger would be hard to reuse in Bevy/Fyrox/Godot or Nexus-style
  backends.

Decision: use P8 as a fixture source, but do not harden JS as the core.

### 4.4 Extract Rust World Core Skeleton

Benefits:

- matches the repository's Rust workspace shape;
- extracts admitted P5 concepts without choosing a renderer;
- gives future adapters a stable type and validation target;
- can support both Onsen-style spatial evidence and Nexus-style event/causal
  evidence through opaque adapter evidence;
- creates a clean place for event/evidence/rollback tests before MCP exposure.

Problem:

- less visually exciting than expanding the prototype;
- must stay small enough not to become a premature engine.

Decision: choose this path.

## 5. P10 Decision

P10 should implement a small Rust crate:

```text
crates/world-core/
```

Workspace package name:

```text
ab-world-core
```

This should be a schema and in-memory ledger skeleton, not a runtime engine.

### 5.1 P10 Scope

P10 should include:

| Area | Minimum implementation |
|---|---|
| Schema constants | `agent_bridge.lswr.world.v0`, `action.v0`, `event.v0`, `verification.v0`, `feedback.v0` |
| Core refs | `WorldId`, `BranchId`, `EntityId`, `ParticipantId`, `ActionId`, `EventId`, `RollbackGroupId` as lightweight wrappers or validated strings |
| Core objects | `WorldRef`, `EntityRef`, `Participant`, `Action`, `Event`, `Verification`, `AdapterEvidence`, `RollbackRecord` |
| Verdicts | `Verified`, `NotVerified`, `Blocked` |
| Validation | reason required for `not_verified`/`blocked`; `verified_to` required only for `verified`; human decisions cannot improve verification |
| Ledger | append event, append verification, query events, query evidence, register rollback group |
| Tests | P8-style add/move/not_verified/blocked/reject/rollback invariants |

The crate should depend only on workspace-safe data dependencies such as
`serde`, `serde_json`, `thiserror`, and possibly `uuid`. It should not depend on
Three.js, Godot, Bevy, Fyrox, browser tooling, MCP, or `ab-bridge`.

### 5.2 P10 Non-Scope

P10 must not:

- register MCP tools;
- expose default-profile tools;
- connect to the P8 browser app;
- implement a renderer;
- implement persistence;
- ingest #94 outcomes;
- revive Step D;
- promote viewport, pixel, hash-chain, or causal-edge fields into global core.

Adapter evidence remains opaque payload plus typed summary.

## 6. Why P10 Before Another Adapter

P8 makes the next risk obvious: every adapter needs the same event, evidence,
and truth-preservation rules.

If we add another adapter first, we will either:

- duplicate P8's JavaScript schema in another language; or
- accidentally let adapter-specific evidence become core.

A small `ab-world-core` crate gives future adapters a neutral target:

```text
adapter-specific state
  -> ab-world-core action/event/verification/ledger
  -> human surface or agent readback
```

This keeps the runtime thesis intact: engines and viewers are adapter surfaces,
not the semantic source of truth.

## 7. P10 Acceptance Gates

| Gate | Requirement |
|---|---|
| `CORE-RS-001` | `ab-world-core` builds as an independent workspace crate |
| `CORE-RS-002` | serde round-trip works for world/action/event/verification/rollback records |
| `CORE-RS-003` | `not_verified` and `blocked` require stable reason codes |
| `CORE-RS-004` | `verified_to` is rejected or absent unless verdict is `verified` |
| `CORE-RS-005` | human accept/reject records cannot mutate prior verification |
| `CORE-RS-006` | adapter evidence can carry Onsen-style visual evidence and Nexus-style causal evidence without either becoming core fields |
| `CORE-RS-007` | rollback group registration and query are represented in the ledger |
| `CORE-RS-008` | crate has no dependency on `ab-bridge`, browser, renderer, MCP, or engine crates |

## 8. P10 Falsifiers

Abort or revise P10 if:

- adding `ab-world-core` requires broad unrelated workspace churn;
- the crate starts embedding Three.js/Web-specific fields as core;
- the crate depends on `ab-bridge` or MCP;
- tests require a browser, Godot, Bevy, or Fyrox runtime;
- the schema cannot express both P8 projection evidence and Nexus event/causal
  evidence without lossy fields;
- human decisions can overwrite verification status;
- rollback is represented only as UI undo, not a ledger-visible record.

## 9. Recommended P10 Task Statement

Create branch/worktree:

```text
codex/lswr-world-core-skeleton
/Users/pallasting/Projects/agent-bridge-lswr-world-core
```

Implement:

```text
crates/world-core/
```

with package:

```text
ab-world-core
```

and only these initial surfaces:

```text
schema types
validation helpers
in-memory event/evidence/rollback ledger
unit tests for P8-derived invariants
```

Do not wire it into `ab-bridge` or any MCP profile until the crate passes
`CORE-RS-001` through `CORE-RS-008`.

## 10. Decision Summary

P8 answered the original practical question: a minimal AI/human interaction
runtime does not need to begin as a full 3D engine. It needs a shared semantic
state, projection adapters, structured events, honest verification, human
feedback, and rollback.

The next bottleneck is no longer visual feasibility. It is portable runtime
semantics.

Therefore P10 should extract a small Rust `ab-world-core` crate before expanding
the web UI, adding another engine adapter, or opening MCP-facing integration.
