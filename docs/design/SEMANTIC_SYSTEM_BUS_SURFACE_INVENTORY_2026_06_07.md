# Semantic System Bus Surface Inventory

**Status:** SSB-0 inventory, read-only planning artifact  
**Date:** 2026-06-07  
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Verification Source

This inventory is based on current Agent-Bridge state on 2026-06-07:

- `capabilities`: Codex desktop, GPT-5.5, `codex-essential`, 84 exposed tools.
- `readiness_audit`: ready, 0 warnings, tool profile drift OK.
- `git_topology_preflight`: clean worktree from `origin/master=16eb806`.
- Existing design docs: Linux Computer Use, LSWR, Event Spine, Work Memory,
  Agent Avatar Protocol.

The inventory is not a complete schema. It identifies which shipped surfaces
already have pieces of the semantic bus contract and where normalization should
start.

Legend:

- `O`: semantic object or state tree exists.
- `F`: affordance or action schema exists.
- `A`: action/result is represented.
- `E`: event or event-like telemetry exists.
- `V`: verification/verdict exists.
- `P`: presentation/handoff surface exists.

## 1. Surface Matrix

| Surface | O | F | A | E | V | P | Current strength | Main gap |
|---|---:|---:|---:|---:|---:|---:|---|---|
| MCP registry and tool profiles | yes | yes | partial | yes | partial | partial | Tool identity, profile exposure, telemetry | No shared action/result block |
| `capabilities` / readiness | yes | no | no | partial | yes | yes | Environment health and setup state | Mostly snapshot, not diff/event |
| `mcp_dispatch_audit` / Tool Atlas | yes | no | no | yes | partial | yes | Tool use/failure observability | Needs event-spine linkage |
| Forum / board | yes | yes | yes | yes | partial | yes | Collaboration state and decisions | Not every state change is typed event |
| Presence / avatar surface | yes | yes | partial | yes | partial | yes | Multi-agent visible state | Needs same object/event IDs as tool bus |
| Work memory | yes | yes | yes | partial | partial | yes | Compression-safe active state | Needs session/object links and event cursors |
| Durable memory graph / Palace | yes | yes | partial | partial | partial | yes | Rich semantic topology and visual state | Needs diff stream and normalized events |
| `desktop_snapshot` | yes | no | no | no | no | partial | Desktop/window/AT-SPI state tree | Needs object IDs and affordance extraction |
| `desktop_verify` | partial | no | no | no | yes | partial | Read-only postcondition verifier | Needs normalized verification packet |
| `vision_grounding_ocr` | partial | no | no | no | partial | partial | Pixel fallback with coordinates | Should attach to semantic object when possible |
| `desktop_invoke` / `desktop_action` | partial | yes | yes | yes | partial | partial | Safe act loop under gates | Output should include normalized action result |
| Mobile UI snapshot/tools | yes | yes | yes | partial | partial | partial | Android/iOS state and mutation primitives | Needs same action/result/verdict schema |
| Browser/CDP tools | yes | yes | yes | partial | partial | partial | DOM and page automation | Needs adapter-neutral object/affordance mapping |
| IDE bridge | yes | yes | yes | yes | partial | yes | Files, selections, diagnostics, commands | Needs event IDs and result verification |
| Git topology preflight | yes | yes | yes | yes | yes | yes | Clean read-only topology/verdict example | Good candidate for normalized action_result |
| LSWR `world_*` | yes | yes | yes | yes | yes | partial | Best mutate/perceive/verify loop | Needs generalized semantic bus wrapper |
| `world_present` / present packet | yes | no | no | yes | yes | yes | Best presentation/no-laundering example | Needs linkage back to global event IDs |
| Event spine snapshot | partial | no | no | yes | yes | yes | Hash-chain explainability model | Needs write-side producers |
| Hooks / instinct observer | yes | no | no | yes | partial | yes | Lifecycle and prompt/tool-use sensing | Needs normalized hook event records |
| Pet/avatar/voice | yes | yes | yes | yes | partial | yes | Embodied presentation/state surface | Needs system object linkage |

## 2. Strongest Existing Patterns

### 2.1 LSWR

LSWR is the strongest current proof of the full loop:

```text
world_patch / world_visibility_query -> stable envelope -> verification verdict
-> world_present -> human/machine presentation packet
```

It already enforces key rules needed globally:

- stable top-level reason;
- `verified_to` only for verified results;
- no success wording for `not_verified` or `blocked`;
- raw details optional but stable envelope preserved.

### 2.2 Linux Computer Use

Linux Computer Use is the strongest OS-substrate proof:

```text
desktop_snapshot -> desktop_invoke / desktop_action -> desktop_verify
```

Its key lesson is bus-first, vision-as-fallback. The missing layer is extracting
stable semantic objects and affordances from snapshot output.

### 2.3 Palace / Memory Graph

Palace is the best user-facing semantic state surface. It already exposes
regions, nodes, relation summaries, health, and maintenance actions. It is a
good read-only pilot for:

```text
snapshot -> diff -> event page -> presentation
```

### 2.4 Git Topology Preflight

`git_topology_preflight` is a clean read-only action/verdict example:

```text
source + target -> merge-base check -> diff summary -> warnings/verdict
```

It is a low-risk candidate for the first normalized `action_result` fixture.

## 3. Gaps By Contract Stage

### Semantic Object

Current state:

- present in many surfaces;
- IDs are inconsistent;
- provenance shape differs per adapter.

Needed:

- stable `object_id`;
- `source_adapter`;
- `object_type`;
- optional relations;
- confidence and observed timestamp.

### Affordance

Current state:

- implicit in tool schemas and UI actions;
- not always emitted as data.

Needed:

- extract affordances as first-class records;
- include risk and gate posture;
- attach expected effect.

### Action

Current state:

- most MCP tools are actions, but outputs are tool-specific.

Needed:

- preserve current payloads;
- add compatibility wrapper block:

```json
{
  "action_result": {
    "schema": "agent_bridge.semantic_bus.action_result.v0",
    "action_id": "...",
    "adapter": "...",
    "verdict": "...",
    "reason": "...",
    "event_ids": []
  }
}
```

### Event

Current state:

- telemetry exists;
- event spine is mostly read-only projection;
- adapter state changes do not all emit typed events.

Needed:

- typed event producers;
- stable cursors;
- hash-chain verifier;
- replay fixtures.

### Verification

Current state:

- strongest in LSWR and `desktop_verify`;
- partial in readiness and topology tools.

Needed:

- shared verdict vocabulary;
- stable reason;
- recover hint where useful;
- no-laundering invariant.

### Memory / Presentation

Current state:

- strong in forum, work memory, Palace, present, voice/avatar;
- linkage to actions/events is uneven.

Needed:

- `source_event_ids`;
- ingestion policy;
- human summary plus machine payload;
- optional artifact reference.

## 4. SSB-0 Findings

1. Agent-Bridge already has enough pieces to define the bus without inventing a
   new product surface.
2. LSWR should be the first action/result normalization pilot.
3. Palace should be the first read-only diff/event pilot.
4. Linux desktop should be the first OS adapter conformance pilot.
5. Git topology preflight should be the first low-risk read-only action fixture.
6. Screenshots/OCR should stay as fallback and contradiction checks, not primary
   state when semantic channels exist.
7. Do not expose more host mutation until normalized verification and event
   records exist.

## 5. Recommended Next Work

Proceed to SSB-1:

- create a small fixture pack for desktop, mobile, LSWR, daemon, Palace, and git;
- add validator tests for required fields and stable vocabulary;
- avoid runtime behavior changes.

Then choose one pilot:

1. LSWR normalized action/result wrapper;
2. Palace semantic diff/event report;
3. Linux desktop object/affordance extraction.

The best immediate order is:

```text
SSB-1 fixture pack
-> SSB-2 Palace read-only diff/event pilot
-> SSB-3 LSWR action_result wrapper
-> SSB-4 Linux adapter conformance
```

Reason:

- SSB-1 gives a stable schema target.
- Palace is high-signal and read-only.
- LSWR already has verification discipline.
- Linux adapter conformance is broader and should follow the schema target.
