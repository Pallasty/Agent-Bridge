# Live Semantic World Runtime - Interaction Feedback Consumption Report MCP Gate Acceptance

**2026-06-15 - role: gate acceptance / docs-only**

Parent documents:
- [Interaction feedback evidence packet consumption](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_EVIDENCE_PACKET_CONSUMPTION_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback consumption report MCP gate](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_GATE_2026_06_15.md)
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)

Forum anchors:
- `#102` post `#3071`: MCP gate design claim.
- `#102` post `#3074`: MCP gate landed at `3e14f86`.
- `#102` post `#3075`: MCP transport-envelope clarification landed at `6a4e5ae`.
- `#102` post `#3079`: this docs-only acceptance review claim.

## 0. Purpose

This review accepts the MCP registration gate for a future all/niche
interaction-feedback consumption report tool.

It does not implement the tool. It does not edit `mcp_tools.rs`, change profile
exposure, deploy a binary, query live runtime state, read files, write state,
write memory, ingest #94 outcomes, mutate Onsen, execute actions, or rewrite
verification verdicts.

## 1. Evidence Inspected

Gate document:

```text
LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_GATE_2026_06_15.md
```

Current gate commit:

```text
6a4e5ae6bfaf47c3820daea17dfa5f7b756dd0c5
docs(lswr): clarify feedback report mcp envelope
```

Relevant accepted surface:

```text
agent_bridge.lswr.interaction_feedback_consumption_report.v0
```

Current repository state:

```text
HEAD/origin/master/github/master = 6a4e5ae6bfaf47c3820daea17dfa5f7b756dd0c5
```

No newer #102 replies after the hash correction in post `#3076`.

## 2. Acceptance Findings

The gate is coherent and implementable because it:

- requires a single explicit `report_input` object;
- rejects paths, URLs, screenshots, runtime handles, action requests, writes,
  #94 ingestion, and Onsen/world-adapter affordances;
- keeps the tool out of default, Codex-essential, lean, Gemini, and hook
  profiles;
- uses `Tier::Niche`;
- wraps MCP transport metadata in an outer envelope;
- leaves the embedded pure report unchanged;
- requires tests for schema rejection, profile gating, laundered verdicts, and
  no side effects.

The transport-envelope clarification resolves the only ambiguity found during
review: once the surface is an MCP tool, `mcp_tool_registered=true` belongs to
the outer envelope, while the embedded pure report may still say
`mcp_tool_registered=false` to describe the underlying pure builder.

## 3. Acceptance Matrix

| Gate | Result | Evidence |
|---|---|---|
| G1: Explicit object input | `PASS` | `report_input` is the only top-level input key. |
| G2: Pure module delegation | `PASS` | Handler must call `build_interaction_feedback_consumption_report(...)`. |
| G3: Transport envelope | `PASS` | Outer MCP envelope is required and embedded report remains unchanged. |
| G4: Profile gating | `PASS` | All/all-dev only; default, Codex-essential, lean, Gemini, and hook profiles hidden. |
| G5: Canonical JSON | `PASS` | Embedded report keeps `json_canonical=true`, `markdown_source=preflight`, and `preflight`. |
| G6: Guardrail visibility | `PASS` | No-store/no-live-runtime/no-#94/no-Onsen guardrails are explicit. |
| G7: Failed gate visibility | `PASS` | Missing input and laundered packet cases must remain blocked or structured errors. |
| G8: No truth laundering | `PASS` | `not_verified` cannot be upgraded by transport or human feedback. |
| G9: No side effects | `PASS` | Store, memory, runtime, #94, Onsen, action, and file/path paths are out of scope. |

## 4. Decision

Decision: `GATE_ACCEPTED_FOR_TIER_NICHE_IMPLEMENTATION`.

This authorizes a separate implementation slice to register:

```text
lswr_interaction_feedback_consumption_report
```

under:

```text
Tier::Niche
```

The implementation must follow the accepted gate exactly. It must not broaden
input shape, expose the tool in default/Codex-essential profiles, read paths,
query live runtime state, write state, ingest #94 outcomes, mutate Onsen, invoke
actions, or rewrite verification verdicts.

## 5. Required Next Implementation Evidence

The next implementation DONE must include:

- code diff for the MCP wrapper;
- schema tests for valid `report_input`;
- rejection tests for unknown keys, paths, URLs, runtime handles, screenshots,
  action/write inputs, #94 inputs, and Onsen/world-adapter inputs;
- profile-gating tests proving all/all-dev visibility and default,
  Codex-essential, codex-lean, gemini-lean, and hook-lifecycle hiding;
- laundered-verdict tests;
- confirmation that the outer envelope has `mcp_tool_registered=true` while the
  embedded pure report remains unchanged;
- `cargo fmt -p ab-bridge --check`;
- interaction-feedback fixture/report regression tests;
- `cargo check -p ab-bridge --all-targets`;
- `git diff --check`;
- fresh tools/list evidence after deploy/reconnect if the implementation is
  deployed for runtime proof.

Do not add file/path input, live runtime lookup, store/memory access, #94
ingestion, Onsen mutation, action execution, or default-profile exposure in the
first registration commit.
