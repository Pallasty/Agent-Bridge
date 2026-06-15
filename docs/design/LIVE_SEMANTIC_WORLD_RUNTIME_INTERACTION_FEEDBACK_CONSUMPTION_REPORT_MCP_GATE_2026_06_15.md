# Live Semantic World Runtime - Interaction Feedback Consumption Report MCP Gate

**2026-06-15 - role: registration gate design / docs-only**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback fixture](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_FIXTURE_2026_06_15.md)
- [Interaction feedback evidence packet consumption](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_EVIDENCE_PACKET_CONSUMPTION_2026_06_15.md)
- [Interaction feedback report surface acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_REPORT_SURFACE_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)

## 0. Purpose

This document defines the gate that must pass before the accepted
module/test-only interaction-feedback consumption report can become an MCP
tool.

It does not implement that tool. It does not edit `mcp_tools.rs`, register a
schema, expose a profile, query a live LSWR runtime, read host paths, write
state, write memory, ingest #94 outcomes, mutate Onsen, or rewrite verification
verdicts.

Current verdict:

```text
READY_FOR_REGISTRATION_DESIGN
```

Implementation status:

```text
NOT_IMPLEMENTED_AS_MCP_TOOL
```

## 1. Candidate MCP Surface

Candidate tool name:

```text
lswr_interaction_feedback_consumption_report
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

Allowed output:

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

- file paths;
- host paths;
- packet paths;
- fixture paths;
- URLs;
- screenshots or image inputs;
- GUI captures;
- runtime handles;
- live runtime host/port values;
- Onsen scene identifiers;
- #94 outcome IDs as an ingestion request;
- patch/action/invoke requests;
- any unknown top-level key other than `report_input`.

The first MCP registration must stay object-only. If file/path input is ever
needed, it requires a separate local file-read policy gate.

## 3. Profile Gate

Candidate exposure:

- `AGENT_BRIDGE_TOOL_PROFILE=all`: visible;
- all-dev/all-profile equivalent: visible if that profile maps to `all`;
- standard/default profile: hidden;
- `codex-essential`: hidden.

The tool must not be added to `CODEX_ESSENTIAL_DIRECT_EXTRAS` or any
codex-essential capability group.

Interaction-feedback consumption remains experimental. Niche/all exposure is
only for deliberate review sessions.

## 4. Safety Boundary

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

## 5. Acceptance Matrix

| Gate | Required Evidence | Acceptance Rule |
|---|---|---|
| G1: Explicit object input | MCP schema requires only `report_input` | No path, URL, screenshot, runtime handle, or unknown key is accepted. |
| G2: Pure module delegation | Handler calls `build_interaction_feedback_consumption_report(...)` | MCP layer does not reimplement weaker gates. |
| G3: Profile gating | Registry tests cover all, standard, and codex-essential | Visible only under all/niche; hidden in default and codex-essential. |
| G4: Canonical JSON | Output includes `json_canonical=true`, `markdown_source=preflight`, and embedded `preflight` | Markdown remains presentation only. |
| G5: Guardrail visibility | Output and Markdown show no-store/no-MCP/no-live-runtime/no-#94/no-Onsen guardrails | Human review can audit the same result. |
| G6: Failed gate visibility | Missing input and laundered packet tests return blocked reports | Failed C1-C5 gates and blockers remain readable. |
| G7: No truth laundering | Tests preserve blocked/unsafe verdicts | Human feedback cannot become verification evidence. |
| G8: No side effects | Unit tests and boundary scan prove no store, memory, runtime, #94, or Onsen calls | Tool is a transport wrapper only. |

## 6. Required Regression Set

Before any MCP registration commit is accepted, run:

```sh
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture -- --nocapture
cargo run -q -p ab-bridge --example lswr_interaction_feedback_consumption_report_smoke -- --format json --assert-golden --assert-read-only
cargo check -p ab-bridge --no-default-features
rustfmt --edition 2021 --check crates/bridge/src/lswr_interaction_feedback.rs crates/bridge/tests/lswr_interaction_feedback_fixture.rs crates/bridge/examples/lswr_interaction_feedback_consumption_report_smoke.rs --config skip_children=true
git diff --check
```

Registration-specific tests must then add:

```sh
cargo test -p ab-bridge lswr_interaction_feedback_consumption_report_mcp -- --nocapture
cargo test -p ab-bridge present_is_niche_opt_in_and_registers_under_all -- --nocapture
```

The exact test names may change with implementation, but the required evidence
is stable:

- all-profile includes the candidate tool;
- standard/default and codex-essential hide it;
- schema accepts only `report_input`;
- handler rejects unknown keys and indirect sources;
- wrong schema returns a structured error;
- missing input returns a blocked report or structured error without live lookup;
- laundered verdict stays blocked and visible.

## 7. Acceptance States

`READY_FOR_REGISTRATION`

All gates above pass, the registry surface is clear, and the implementation is a
narrow object-only transport wrapper.

`READY_FOR_REGISTRATION_DESIGN`

The gate design is ready, but no MCP registration has been implemented. This is
the current state.

`NOT_READY`

Any profile, schema, side-effect, or no-laundering gate is missing.

`OUT_OF_SCOPE`

The requested implementation adds live runtime lookup, file/path input, store or
memory writes, #94 ingestion, Onsen mutation, action execution, or
default-profile/codex-essential exposure.

## 8. First Registration Plan

When this gate is accepted and the MCP registry surface is available, the first
implementation should:

1. Register `lswr_interaction_feedback_consumption_report` as `Tier::Niche`.
2. Accept exactly one `report_input` JSON object.
3. Reject unknown top-level keys before building a report.
4. Call `build_interaction_feedback_consumption_report(&report_input)`.
5. Return the report unchanged.
6. Add profile-gating and schema tests before posting DONE.

Do not add file input, runtime discovery, store/memory access, #94 ingestion, or
default-profile exposure in the first registration commit.
