# Live Semantic World Runtime - Interaction Feedback Consumption Report MCP Gate

**2026-06-15 - role: registration gate design / docs-only**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback fixture](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_FIXTURE_2026_06_15.md)
- [Interaction feedback evidence packet consumption](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_EVIDENCE_PACKET_CONSUMPTION_2026_06_15.md)
- [Interaction feedback report surface acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_REPORT_SURFACE_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report MCP gate acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_GATE_ACCEPTANCE_2026_06_15.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)

Forum anchors:
- `#102` post `#3066`: pure report builder landed.
- `#102` post `#3069`: report builder accepted as module/test-only.
- `#102` post `#3071`: MCP gate design claim.
- `#102` post `#3079`: MCP gate acceptance review claim.
- `#102` post `#3080`: MCP gate accepted for Tier::Niche implementation.
- `#102` post `#3082`: MCP wrapper source implementation claim.
- `#102` post `#3085`: MCP wrapper source implementation DONE.
- `#102` post `#3088`: deployed `.real` runtime verification DONE.

## 0. Purpose

This document defines the gate that must pass before the accepted
module/test-only interaction-feedback consumption report can become an MCP
tool.

It does not implement that tool. It does not edit `mcp_tools.rs`, register a
schema, expose a profile, query a live LSWR runtime, read host paths, write
state, write memory, ingest #94 outcomes, mutate Onsen, or rewrite verification
verdicts.

Current decision:

```text
GATE_ACCEPTED_FOR_TIER_NICHE_IMPLEMENTATION
```

Implementation status:

```text
DEPLOYED_AND_RUNTIME_VERIFIED
```

Runtime verification summary:

```text
implementation_commit=ba0d0703e7c2ff107f0fe08a2cb4813c3fdcc15e
deploy_target=/Users/pallasting/.local/bin/agent-bridge.real
all_profile_tools_list=present
all_dev_tools_list=present
standard_profile_tools_list=absent
codex_essential_tools_list=absent
fixture_call=accepted
packet_call=accepted
preflight_call=accepted
missing_input_call=structured_error
multiple_input_call=structured_error
forbidden_source_call=structured_error
laundered_verdict_call=blocked_report_visible
outer_mcp_tool_registered=true
embedded_pure_report_mcp_tool_registered=false
writes_state=false
live_runtime_lookup_attempted=false
```

## 1. Candidate MCP Surface

Candidate tool name:

```text
lswr_interaction_feedback_consumption_report
```

Required tier:

```text
Tier::Niche
```

Allowed input shape:

```json
{
  "report_input": {}
}
```

`report_input` must be one explicit JSON object matching exactly one of:

- `agent_bridge.lswr.interaction_feedback_fixture.v0`;
- `agent_bridge.lswr.interaction_feedback_evidence_packet.v0`;
- `agent_bridge.lswr.interaction_feedback_consumption_preflight.v0`;
- a wrapper object with exactly one accepted `fixture` or `packet` object.

Allowed embedded report:

```text
agent_bridge.lswr.interaction_feedback_consumption_report.v0
```

The MCP layer may only call:

```text
build_interaction_feedback_consumption_report(...)
```

It must not weaken or reimplement the preflight gates.

## 2. Rejected Inputs

The schema and handler must reject:

- zero accepted input objects;
- more than one accepted input object;
- raw strings as input;
- file paths;
- host paths;
- packet paths;
- fixture paths;
- preflight paths;
- URLs;
- screenshots or image inputs;
- OCR payloads;
- GUI captures;
- runtime handles;
- live runtime host/port values;
- Onsen scene identifiers;
- #94 outcome IDs as an ingestion request;
- patch/action/invoke/write requests;
- any unknown top-level key other than `report_input`.

Forbidden input keys include:

```text
path
file
file_path
host_path
fixture_path
packet_path
preflight_path
url
runtime
runtime_url
live_runtime
host
gui_capture
screenshot
image
ocr
action
patch
invoke
write
dry_run
outcome_id
onsen_scene
```

The first MCP registration must stay object-only. If file/path input is ever
needed, it requires a separate local file-read policy gate.

## 3. Output Contract

Success output should be an MCP transport envelope:

```json
{
  "schema": "agent_bridge.lswr.interaction_feedback_consumption_report_mcp.v0",
  "tool": "lswr_interaction_feedback_consumption_report",
  "tier": "niche",
  "transport": "mcp",
  "mcp_tool_registered": true,
  "writes_state": false,
  "store_access_required": false,
  "live_runtime_lookup_attempted": false,
  "report_schema": "agent_bridge.lswr.interaction_feedback_consumption_report.v0",
  "report": {}
}
```

The embedded `report` must be the pure report object:

```text
agent_bridge.lswr.interaction_feedback_consumption_report.v0
```

The MCP wrapper must not mutate the embedded pure report. In particular, the
pure report may keep `mcp_tool_registered=false` to describe the underlying
report builder, while the outer MCP envelope records that the transport is
registered.

The embedded report must include:

- `preflight`;
- `markdown`;
- `accepted`;
- `preflight_verdict`;
- `world_verdict`;
- `guardrails`;
- `acceptance_matrix`;
- `failure_reasons`;
- `blockers`;
- `readback`;
- `json_canonical=true`;
- `markdown_source=preflight`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`;
- `implicit_live_runtime_lookup_attempted=false`.

Wrong schema or forbidden input must return a structured JSON error before
calling the report builder. Missing input may return a structured error or a
blocked report, but it must not query live runtime state.

## 4. Profile Gate

Candidate exposure:

| Profile/toolset | Expected |
|---|---|
| `AGENT_BRIDGE_TOOL_PROFILE=all` | visible |
| `AGENT_BRIDGE_TOOLSET=all-dev` | visible |
| standard/default profile | hidden |
| `AGENT_BRIDGE_TOOLSET=codex-essential` | hidden |
| `AGENT_BRIDGE_TOOLSET=codex-lean` | hidden |
| `AGENT_BRIDGE_TOOLSET=gemini-lean` | hidden |
| `AGENT_BRIDGE_TOOLSET=hook-lifecycle` | hidden |

The tool must not be added to:

- `CODEX_ESSENTIAL_DIRECT_EXTRAS`;
- Codex essential capability groups;
- lean profile allowlists;
- hook lifecycle allowlists.

Interaction-feedback consumption remains experimental. Niche/all exposure is
only for deliberate review sessions.

## 5. Safety Boundary

The tool must preserve the module/test-only safety contract:

- read-only;
- no store access;
- no memory write;
- no MCP-to-MCP call;
- no live runtime lookup;
- no screenshot requirement;
- no file/path read;
- no #94 ingestion;
- no Onsen/world mutation;
- no verification verdict rewrite.

If the preflight reports `world_verdict=not_verified`, the MCP report must show
`not_verified`. If the input is laundered and claims `verified`, the report may
display that unsafe value only as the blocked preflight result; it must not
convert the report to success.

## 6. Acceptance Matrix

| Gate | Required Evidence | Acceptance Rule |
|---|---|---|
| G1: Explicit object input | MCP schema requires only `report_input` | No path, URL, screenshot, runtime handle, or unknown key is accepted. |
| G2: Pure module delegation | Handler calls `build_interaction_feedback_consumption_report(...)` | MCP layer does not reimplement weaker gates. |
| G3: Transport envelope | Output wraps the pure report in an MCP envelope | `mcp_tool_registered=true` belongs to the envelope; embedded pure report remains unchanged. |
| G4: Profile gating | Registry tests cover all, all-dev, standard/default, Codex-essential, lean, Gemini, and hook profiles | Visible only under all/niche; hidden elsewhere. |
| G5: Canonical JSON | Embedded report includes `json_canonical=true`, `markdown_source=preflight`, and embedded `preflight` | Markdown remains presentation only. |
| G6: Guardrail visibility | Output and Markdown show no-store/no-live-runtime/no-#94/no-Onsen guardrails | Human review can audit the same result. |
| G7: Failed gate visibility | Missing input and laundered packet tests return blocked reports or structured errors | Failed gates and blockers remain readable when a report is returned. |
| G8: No truth laundering | Tests preserve blocked/unsafe verdicts | Human feedback cannot become verification evidence. |
| G9: No side effects | Unit tests and boundary scan prove no store, memory, runtime, #94, or Onsen calls | Tool is a transport wrapper only. |

## 7. Required Regression Set

Before any MCP registration commit is accepted, run:

```bash
cargo fmt -p ab-bridge --check
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture -- --nocapture
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_consumption_report -- --nocapture
cargo run -q -p ab-bridge --example lswr_interaction_feedback_consumption_report_smoke -- --format json --assert-golden --assert-read-only
cargo check -p ab-bridge --all-targets
cargo check -p ab-bridge --no-default-features
git diff --check
```

Registration-specific tests must then add:

```bash
cargo test -p ab-bridge lswr_interaction_feedback_consumption_report_mcp -- --nocapture
```

The exact test names may change with implementation, but the required evidence
is stable:

- all-profile includes the candidate tool;
- all-dev includes the candidate tool;
- standard/default, Codex-essential, codex-lean, gemini-lean, and
  hook-lifecycle hide it;
- schema accepts only `report_input`;
- handler rejects unknown keys and indirect sources;
- wrong schema returns a structured error;
- missing input returns a blocked report or structured error without live
  lookup;
- laundered verdict stays blocked and visible;
- outer envelope has `mcp_tool_registered=true`, while embedded pure report
  remains unchanged;
- existing interaction-feedback fixture/preflight/report tests still pass.

## 8. Required Runtime Verification

After implementation, deploy/reconnect before runtime evidence. Use fresh MCP
stdio `tools/list` probes:

- all-profile includes `lswr_interaction_feedback_consumption_report`;
- all-dev includes `lswr_interaction_feedback_consumption_report`;
- standard/default excludes it;
- Codex-essential excludes it;
- codex-lean excludes it;
- gemini-lean excludes it;
- hook-lifecycle excludes it.

Runtime call probes must include:

- valid explicit fixture object under `report_input`;
- valid explicit packet object under `report_input`;
- valid explicit preflight object under `report_input`;
- missing input;
- multiple nested accepted input keys;
- every forbidden key class;
- laundered verdict packet.

Every rejected runtime call must report `writes_state=false` or an equivalent
no-write guardrail when a payload is returned.

## 9. Acceptance States

`READY_FOR_REGISTRATION`

All gates above pass, the registry surface is clear, and the implementation is a
narrow object-only transport wrapper.

`GATE_DEFINED_IMPLEMENTATION_HOLD`

The gate design is ready, but no MCP registration has been implemented.

`GATE_ACCEPTED_FOR_TIER_NICHE_IMPLEMENTATION`

The gate is accepted for a separate implementation slice. This is the current
state.

`NOT_READY`

Any profile, schema, side-effect, or no-laundering gate is missing.

`OUT_OF_SCOPE`

The requested implementation adds live runtime lookup, file/path input, store or
memory writes, #94 ingestion, Onsen mutation, action execution, or
default-profile/codex-essential exposure.

## 10. First Registration Plan

When this gate is accepted and the MCP registry surface is available, the first
implementation should:

1. Register `lswr_interaction_feedback_consumption_report` as `Tier::Niche`.
2. Accept exactly one `report_input` JSON object.
3. Reject unknown top-level keys before building a report.
4. Reject path, URL, screenshot, runtime, action, write, #94, and Onsen input
   affordances before building a report.
5. Call `build_interaction_feedback_consumption_report(&report_input)`.
6. Return an MCP envelope with the pure report embedded unchanged.
7. Add profile-gating and schema tests before posting DONE.

Do not add file input, runtime discovery, store/memory access, #94 ingestion, or
default-profile exposure in the first registration commit.
