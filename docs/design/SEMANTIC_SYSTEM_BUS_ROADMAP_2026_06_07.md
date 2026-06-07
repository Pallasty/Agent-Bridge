# Agent-Bridge Semantic System Bus Roadmap

**Status:** design roadmap, Linux-first substrate, verify-first execution  
**Date:** 2026-06-07  
**Scope:** Agent-Bridge system/app interaction direction after LSWR Step D and
Codex toolset deployment.

Related documents:
- [Linux Computer Use](LINUX_COMPUTER_USE.md)
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [LSWR MVP Shape](LIVE_SEMANTIC_WORLD_RUNTIME_MVP_SHAPE_2026_06_06.md)
- [Cross-project Event Spine Roadmap](CROSS_PROJECT_EVENT_SPINE_ROADMAP_2026_05_27.md)
- [Work Memory Scratchpad](../DESIGN-work-memory-scratchpad-2026-05-23.md)
- [Agent Avatar Protocol](../RFC-v24-agent-avatar-protocol.md)
- [Palace Diff Pilot](SEMANTIC_SYSTEM_BUS_PALACE_DIFF_PILOT_2026_06_07.md)

## 0. Decision

Agent-Bridge should evolve toward an AI-readable **semantic system bus**, not a
screenshot-first computer-use wrapper.

Humans should still interact through visual, audio, keyboard, pointer, gesture,
and review surfaces. AI agents should primarily consume and act on structured
semantic state: object trees, affordances, action schemas, event diffs,
verification packets, memory links, and presentation records.

Screenshots, screenshots plus OCR, and pixel grounding remain important, but
their role is:

1. fallback when semantic state is missing or unreliable;
2. visual acceptance evidence for what a human actually saw;
3. contradiction detection when semantic state and rendered UI disagree.

The target loop is:

```text
Semantic Object -> Affordance -> Action -> Event -> Verification -> Memory/Presentation
```

This is the common shape that desktop, mobile, browser, LSWR, Palace, memory,
daemon, IDE, and future app adapters should map into.

## 1. Why Linux-first

macOS and Windows have stronger traditional app coverage. Linux has the better
shape for an AI-native substrate when we control the runtime:

- composable daemons, sockets, files, logs, systemd units, DBus, procfs, and
  container boundaries;
- inspectable desktop and process state through wlroots/sway, AT-SPI, and
  structured IPC;
- natural local and remote automation through CLI and service composition;
- clearer path from "app" to "capability node" that an AI can call directly.

The strategic distinction:

```text
macOS / Windows: strongest traditional app ecosystem
Linux: strongest capability ecosystem for AI-native composition
```

The product posture should therefore be:

- Linux-first for the reference semantic bus and conformance harness.
- macOS/Windows as adapter targets that map AX/UIA/app-specific surfaces into
  the same Agent-Bridge schemas.
- Visual/OCR fallback retained across all platforms.

## 2. Current Baseline

Agent-Bridge already has several pieces of the bus, but they are not yet a single
uniform layer.

| Area | Current state | Gap |
|---|---|---|
| MCP tool bus | Mature tool registry, profile/toolset routing, Codex/Gemini/Claude slices, dispatch audit, tool atlas | Tools still expose separate local schemas rather than one system-state contract |
| Memory/coordination | Memory, forum, presence, work memory, graph topology, Palace | Strong semantic state, but not all state changes emit typed events |
| Desktop computer use | `desktop_snapshot`, `desktop_verify`, OCR grounding, gated action/invoke paths | Good act loop, but object/action/event/verdict schema differs from LSWR and mobile |
| Mobile bridge | Android/iOS health, UI snapshot, screenshot, click/input/install/log tools | Useful adapter, but not unified with desktop action/result contract |
| LSWR | `world_query`, `world_patch`, `world_visibility_query`, `world_present` | Best current example of mutate/perceive/present; needs generalization beyond world runtime |
| Event spine | Read-only snapshot and roadmap exist | Needs typed producers and replay/conformance gates |
| Presentation | present packets, Palace, avatar/pet surfaces, voice lane | Strong output layer, but not every action/result has a presentation packet |
| Hooks | Codex hooks, precompact/session-end, instinct observer, setup-state | Good lifecycle sensors, but not yet normalized as bus events |

Distance estimate:

- Research prototype and dogfood substrate: past halfway.
- Linux-first semantic interaction substrate: directionally clear; ready for
  formal schema and narrow implementation slices.
- Cross-platform product: early; needs adapter conformance, event streaming,
  and schema stability.

## 3. Unified Contract

### 3.1 Semantic Object

A semantic object is any stateful thing an AI can reason about:

- desktop window, accessible element, mobile UI node, browser DOM node;
- file, process, daemon, socket, systemd unit, git branch;
- memory node, Palace region, forum thread, work memory slot;
- LSWR entity, space, participant, patch target;
- avatar/pet surface, voice request, notification.

Minimum fields:

```text
schema
object_id
object_type
source_adapter
label
state
relations
confidence
observed_at
provenance
```

### 3.2 Affordance

An affordance is an action the object says is available.

Examples:

- click, type, select, expand, focus, invoke;
- patch, rollback, branch, query visibility;
- restart service, inspect health, open file, reveal range;
- approve, reject, comment, present, speak.

Minimum fields:

```text
affordance_id
object_id
action_type
args_schema
risk_level
requires_gate
expected_effect
```

### 3.3 Action

An action is an attempted mutation or query with explicit provenance.

Minimum fields:

```text
action_id
actor
adapter
affordance_id
arguments
precondition
gate
started_at
```

### 3.4 Event

An event records what changed or what was observed.

Minimum fields should align with the event-spine roadmap:

```text
event_id
ts
source
actor
project
event_type
subject_id
payload_json
source_event_ids
prev_hash
hash
```

Events should include both AI actions and human input when available.

### 3.5 Verification

Verification is the trust boundary.

Every claim that matters should resolve to:

| Verdict | Meaning |
|---|---|
| `verified` | Evidence confirms the claim in the relevant context |
| `not_verified` | Evidence contradicts or cannot confirm the claim |
| `blocked` | The system refused or could not safely attempt the action |

Minimum fields:

```text
verdict
reason
method
evidence
verified_to
recover
raw_available
```

Rules:

- never turn lower-layer `not_verified` into success;
- preserve stable top-level `reason` even when raw details are omitted;
- emit `verified_to` only for verified claims;
- provide a `recover` hint when the next local step is obvious.

### 3.6 Memory/Presentation

The final step is not only data storage. It is a human/agent handoff surface.

Examples:

- `present_packet`;
- Palace card or graph node;
- work memory;
- forum decision/finding;
- voice/pet/avatar cue;
- replay/audit record.

Minimum fields:

```text
presentation_id
source_event_ids
human_summary
machine_payload
ingestion
artifact
created_at
```

## 4. Architecture

```text
Adapters
  Linux desktop    macOS AX       Windows UIA      Android/iOS
  browser/DOM      IDE            git/process      LSWR world
       |              |                |              |
       v              v                v              v
Semantic Bus Normalizer
  object tree -> affordances -> actions -> events -> verification
       |
       v
Event Spine / Store
  append-only events, hashes, cursors, replay, audit
       |
       +--> Memory / work memory / forum sediment
       +--> Palace / present / voice / avatar surfaces
       +--> Tool/profile/adapter telemetry
```

The normalizer is the missing center. It does not replace existing tools. It
defines the schemas and conformance gates they should gradually adopt.

## 5. Verification Gates

Do not add broad automation until these gates exist.

### Gate A - Inventory

Produce a current-state inventory of semantic surfaces:

- tool name;
- source adapter;
- read/write;
- state schema;
- action schema;
- event output;
- verification behavior;
- risk/gate posture;
- profile exposure.

### Gate B - Schema Fixture

Define one small `agent_bridge.semantic_bus.v0` fixture family:

- desktop accessible object;
- mobile UI node;
- LSWR world entity;
- process/daemon object;
- Palace memory graph node.

Each fixture must round-trip through JSON and be small enough for an LLM to read.

### Gate C - Event Diff

For one safe read-only adapter, show:

```text
snapshot_1 -> snapshot_2 -> semantic diff -> event page
```

This should start with Palace/memory graph or daemon/process state, not host GUI
mutation.

### Gate D - Action Result Contract

For one already-safe action path, show:

```text
affordance -> action -> result -> verification -> presentation
```

Best candidates:

- LSWR `world_present` over known envelopes;
- `git_topology_preflight` as read-only topology action;
- `desktop_verify` read-only verification over an existing selector.

### Gate E - Adapter Conformance

Add a small conformance runner:

```text
adapter emits objects
adapter emits affordances
action/result keeps stable IDs
verification has verdict/reason
presentation is optional but linked when present
```

This should be a test harness first, not a new product surface.

## 6. Implementation Slices

### SSB-0 - Current-state inventory

Deliverable:

- `docs/design/SEMANTIC_SYSTEM_BUS_SURFACE_INVENTORY_2026_06_07.md`
- no code changes required;
- based on `capabilities`, `readiness_audit`, tool registry, and existing docs.

Goal:

Identify which existing surfaces already map to object/action/event/verification
and which are raw tools only.

### SSB-1 - Schema fixture pack

Deliverable:

- fixtures under `crates/bridge/fixtures/semantic_bus/`;
- read-only validator test;
- no tool behavior change.

Goal:

Create shared examples that future adapters and LLM prompts can target.

### SSB-2 - Read-only event diff pilot

Deliverable:

- one read-only semantic diff tool or report over Palace/memory/daemon state;
- stable `event_id`, `subject_id`, `event_type`, `verdict` where applicable.

Initial landing:

- Palace first, via `GET /api/semantic-events`;
- browser baseline stored in localStorage, server remains stateless/read-only;
- footer pulse exposes object/event counts and graph deltas on the 7979 surface.

Goal:

Move from pull-only snapshots to snapshot-diff-event without host mutation.

### SSB-3 - Action/result normalization

Deliverable:

- wrap one existing mature tool family so its output includes a normalized
  `action_result` block;
- keep existing payload intact for compatibility.

Best candidate:

- LSWR `world_*` plus `world_present`, because no-laundering and presentation
  are already tested.

Initial landing:

- [Semantic System Bus LSWR Action Result Pilot](SEMANTIC_SYSTEM_BUS_LSWR_ACTION_RESULT_2026_06_07.md);
- `world_query`, `world_visibility_query`, and `world_patch` now emit
  `agent_bridge.semantic_bus.action_result.v0`;
- `world_present` preserves the normalized action result in the machine packet
  while keeping verdicts tied to the original world tool verification.

### SSB-4 - Linux-first adapter conformance

Deliverable:

- conformance checks for `desktop_snapshot`, `desktop_verify`,
  `vision_grounding_ocr`, and selected process/daemon surfaces;
- no broad host mutation.

Goal:

Make Linux the reference substrate for semantic bus behavior.

### SSB-5 - Cross-platform mapping memo

Deliverable:

- macOS AX and Windows UIA mapping memo;
- required fields and known gaps;
- adapter-specific fallbacks.

Goal:

Keep macOS/Windows as coverage adapters without letting them fragment the core
schema.

## 7. Non-goals

- Do not make screenshots the primary architecture.
- Do not expose broad host mutation as a default MCP surface.
- Do not replace existing mature tools before a compatibility wrapper exists.
- Do not build a new UI before the semantic bus inventory and schema fixtures
  are grounded.
- Do not treat Linux-first as Linux-only.

## 8. Immediate Recommendation

Start with SSB-0 and SSB-1.

Reason:

- They are low-risk and documentation/test-heavy.
- They preserve current tool compatibility.
- They give every later adapter a common target.
- They make the next code slice measurable instead of conceptual.

After SSB-0/SSB-1, choose one pilot:

1. **LSWR pilot**: normalize `world_*` action/result and present packets.
2. **Palace pilot**: semantic graph diff/event stream for memory topology.
3. **Linux desktop pilot**: normalized desktop object/affordance fixtures.

The LSWR pilot is the most mature. The Palace pilot is the best user-facing
state surface. The Linux desktop pilot is the best system-substrate proof.
