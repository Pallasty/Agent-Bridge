# Live Semantic World Runtime - Interaction Feedback Evidence Packet Consumption

**2026-06-15 - role: consumption acceptance plan / CLI-only read-only surface + report acceptance + module acceptance**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback fixture](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_FIXTURE_2026_06_15.md)
- [Interaction feedback report surface acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_REPORT_SURFACE_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)

Forum anchors:
- `#102` post `#3044`: pure evidence packet helper landed at `fe70e8d`.
- `#102` post `#3047`: protocol and fixture docs synced at `b195850`.
- `#102` post `#3049`: start notice for this consumption plan.
- `#102` post `#3052`: start notice for pure consumption preflight helper.
- `#102` post `#3060`: reconciled report-surface acceptance review claim.
- `#102` post `#3066`: pure report builder landed at `cc2394c`.
- `#102` post `#3068`: module/test-only acceptance review claim.
- `#104` post `#2412`: adjacent BioCortex/LSWR handoff remains blocked on
  external onsen Step B source, so this slice advances only the independent
  read-only interaction-feedback consumer.

## 0. Purpose

This plan defines how later surfaces may consume:

```text
agent_bridge.lswr.interaction_feedback_evidence_packet.v0
```

The packet is currently local evidence over a fixture:

```text
fixture -> validation envelope -> Markdown report -> evidence packet
```

This document does not register a tool, add a writer, query a live runtime, or
ingest outcomes. It defines the acceptance conditions for any future consumer.

## 1. Consumption Thesis

The evidence packet should be treated as a review object, not a world adapter.

It is useful because it lets humans and agents inspect the same interaction loop
without screenshots:

- what the human selected;
- what the AI proposed;
- what changed visibly;
- which verification clause failed;
- what the human rejected or annotated;
- what the next revision should cite.

The packet must not become a laundering path from human preference to verified
world state. Human feedback can guide the next revision, but it cannot upgrade
`not_verified` to `verified`.

## 2. Allowed Consumers

### A. Example and smoke runner

Current state. The example consumes a checked-in fixture and emits the packet.

Allowed:

- local CLI/example execution;
- test fixtures;
- JSON output;
- Markdown output through the embedded packet field.

Not allowed:

- live runtime queries;
- file writes beyond normal command stdout;
- memory writes;
- MCP registration.

### B. Future read-only report surface

This is acceptable only after explicit review.

Allowed input:

```json
{
  "fixture": {
    "schema": "agent_bridge.lswr.interaction_feedback_fixture.v0"
  }
}
```

or:

```json
{
  "interaction_pages": {
    "events": {"schema": "agent_bridge.lswr.event_page.v0"},
    "feedback": {"schema": "agent_bridge.lswr.feedback_page.v0"},
    "presentation": {"schema": "agent_bridge.lswr.presentation_page.v0"},
    "verification": {"schema": "agent_bridge.lswr.verification_page.v0"}
  }
}
```

The consumer must reject implicit live runtime lookup. If a later live adapter is
needed, it must produce one of the accepted explicit input objects first.

### C. Future UI or panel view

A UI view may render the packet only as read-only review state.

Required visible sections:

- packet schema and fixture ID;
- validation verdict and failure reasons;
- guardrails;
- readback summary;
- Markdown report;
- embedded envelope link or expandable detail;
- explicit no-write note.

The UI must not present the packet as proof that a world action succeeded unless
the packet's validation and lower-layer verification both say so.

## 3. Required Output Shape

Any future consumer should preserve these fields:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_evidence_packet.v0",
  "fixture_id": "lswr_interaction_feedback_loop_001",
  "valid": true,
  "failure_reasons": [],
  "guardrails": {
    "read_only": true,
    "writes_state": false,
    "store_access_required": false,
    "mcp_tool_registered": false,
    "feedback_changes_world_verdict_allowed": false
  },
  "readback": {
    "latest_verification_verdict": "not_verified",
    "latest_human_decision": "reject",
    "revision_should_cite": [
      "verify_patch_arrival_bath_move_001",
      "fb_arrival_crowded_001"
    ]
  },
  "note": "local evidence only: pure fixture render, no MCP call, no store access, no memory write"
}
```

Consumers may add display metadata, but they must not remove guardrails or
rewrite readback fields.

## 4. Forbidden Behavior

A consumer is not accepted if it:

- queries a live LSWR host implicitly;
- calls `memory_save`;
- accesses `StateStore` or `SqliteStore`;
- writes files or database rows;
- opens a `dry_run=false` path;
- registers an MCP tool without a separate all-profile/niche gate review;
- exposes the packet in the default profile;
- routes the packet to #94 ingestion;
- mutates Onsen or any world adapter;
- rewrites a failed world verdict because a human accepted or rejected a
  presentation.

## 5. Acceptance Gates

### C1: Explicit input only

Given no fixture or accepted interaction pages, the consumer returns a structured
`blocked` or `not_verified` result. It must not query live state on its own.

### C2: Guardrails preserved

Given a valid packet, the consumer output still shows `writes_state=false`,
`store_access_required=false`, and `feedback_changes_world_verdict_allowed=false`.

### C3: No verification laundering

Given `readback.latest_verification_verdict="not_verified"` and human feedback,
the consumer still reports the world result as not verified.

### C4: Agent can choose the next revision source

Given the packet, an agent can identify the failed verification ID and feedback
ID that the next patch should cite.

### C5: Human can audit the same result

Given the rendered view, a human can see the same failed clause, feedback issue,
and next revision sources without reading raw JSON.

## 6. Pure Preflight Helper

The first implementation slice is the pure consumer preflight:

```text
build_interaction_feedback_packet_consumption_preflight(...)
```

It accepts:

- an explicit fixture;
- an explicit evidence packet;
- a wrapper object with `fixture`;
- a wrapper object with `packet`.

It returns:

- `schema=agent_bridge.lswr.interaction_feedback_consumption_preflight.v0`;
- `preflight_verdict=accepted|blocked`;
- `world_verdict`, copied from packet readback or `not_verified` when input is
  missing;
- guardrails proving no live runtime lookup, no store access, no MCP
  registration, no default-profile exposure, and no #94 ingestion;
- C1-C5 acceptance matrix;
- structured `failure_reasons`;
- the resolved packet when accepted.

The preflight remains outside MCP registration. It does not query live runtime
state and does not write files, memory, or store rows.

## 7. CLI-Only Read-Only Surface

The same pure preflight is exposed through an explicit file-input CLI:

```text
agent-bridge bio-cortex lswr-interaction-feedback-consumption-preflight \
  --input-json crates/bridge/tests/fixtures/lswr_interaction_feedback_fixture_v0.json \
  --json
```

Accepted inputs are unchanged: an explicit fixture, an explicit evidence packet,
or a wrapper object with `fixture` or `packet`.

This CLI surface is still not an MCP tool and not a default-profile capability.
It does not query live LSWR state, register a tool, access `StateStore` or
`SqliteStore`, write memory, write approval state, route to #94 ingestion, or
mutate Onsen/world runtime state. Text output is a compact summary; `--json`
prints the preflight envelope for review automation.

## 8. Report Surface Acceptance

The report-surface acceptance review is tracked in:

```text
LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_REPORT_SURFACE_ACCEPTANCE_2026_06_15.md
```

Current decision:

```text
GO_FOR_PURE_MODULE_REPORT_SURFACE
```

This approves a pure Markdown/report builder over explicit input and accepted
preflight output. It does not approve MCP registration, default-profile exposure,
live runtime lookup, writes, or #94 ingestion.

## 9. Pure Report Builder Slice

The pure report-builder slice implements:

```text
agent_bridge.lswr.interaction_feedback_consumption_report.v0
```

Module helpers:

```text
build_interaction_feedback_consumption_report(...)
render_interaction_feedback_consumption_preflight_report(...)
```

The builder accepts an explicit fixture, evidence packet, wrapper object, or
already-built preflight object. It derives Markdown from the canonical
preflight object and keeps JSON as the authority.

Smoke path:

```text
cargo run -p ab-bridge --example lswr_interaction_feedback_consumption_report_smoke -- --assert-golden --assert-read-only
```

The slice remains pure: no MCP registration, no runtime lookup, no file/path
input, no store/memory write, no #94 ingestion, no Onsen mutation, and no
verification verdict rewrite.

## 10. Recommended Next Slice

The pure report builder is accepted as module/test-only in:

```text
LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md
```

Current decision:

```text
ACCEPTED_MODULE_TEST_ONLY
```

Accepted surfaces:

- `agent_bridge.lswr.interaction_feedback_consumption_report.v0`;
- `build_interaction_feedback_consumption_report(...)`;
- `render_interaction_feedback_consumption_preflight_report(...)`;
- golden Markdown fixture;
- stdout-only smoke example.

This still does not approve MCP registration, default-profile exposure, live
runtime lookup, file/path input, store/memory writes, #94 ingestion, Onsen
mutation, or verification verdict rewrite.

## 11. Recommended Next Slice

```text
Design a separate MCP registration gate for an all/niche read-only tool.
```

The gate design is tracked in:

```text
LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_GATE_2026_06_15.md
```

Do not start with a live runtime adapter, writer, default-profile tool, or #94
ingestion path.
