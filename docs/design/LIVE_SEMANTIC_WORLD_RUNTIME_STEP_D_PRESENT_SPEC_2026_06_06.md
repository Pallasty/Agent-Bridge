# Live Semantic World Runtime - Step D Present Spec

**2026-06-06 - role: expression-boundary design**

Parent documents:
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Phase 0 Step C Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_C_SPEC_2026_06_05.md)
- [MVP Shape After Phase 0](LIVE_SEMANTIC_WORLD_RUNTIME_MVP_SHAPE_2026_06_06.md)
- [Landing Plan](LIVE_SEMANTIC_WORLD_RUNTIME_LANDING_PLAN_2026_06_05.md)

Board anchors:
- `#102`: Phase 0 A/B/C acceptance, Step C final accepted at `5037e01`.
- `#105`: MVP shape after Phase 0.
- `#92`: output/expression lane, `present()` E-ladder.
- `#94`: verified-outcome stream from output lane to memory/training substrate.

## 0. Purpose

Step C made the live semantic world visible to agents through `world_query`,
`world_patch`, and `world_visibility_query`.

Step D makes those same world results **legible to humans** through the existing
output/expression lane without changing their verification meaning.

This is an expression boundary, not a learning boundary.

Step D answers:

> Can an agent take an honest `world_*` result and present it to a human as a
> reviewable artifact while preserving `verified`, `not_verified`, `blocked`,
> `verify.method`, `verified_to`, and machine-readable reasons?

## 1. Current Verified State

Accepted inputs:

- Step C is final accepted in forum `#102` post `#2467`.
- Agent-Bridge master contains the Step C surface at `5037e01`.
- `world_*` tools remain `Tier::Niche`: hidden from normal profiles, exposed in
  `AGENT_BRIDGE_TOOL_PROFILE=all`.
- Not-verified reasons survive raw stripping:
  - top-level `reason`;
  - `verify.evidence.host_reason`;
  - `include_raw=false` still preserves both.

Relevant output-lane state:

- `present()` is an existing Niche output tool for static/interactive artifacts.
- `present_replay` and related present surfaces provide audit/replay shape.
- `present_outcomes` and `present_outcomes_ingest` already exist for verified
  outcome flow.
- That means Step D must be careful: using `present()` may create output-lane
  sidecars, but LSWR must not treat that as permission to ingest world results
  into memory/training automatically.

## 2. Non-goals

Step D does not:

- add new `world_*` tools;
- modify the Onsen host;
- call #94 ingestion automatically;
- build branch/rollback UI;
- extract Rust runtime core;
- add Nexus adapter;
- create a full 3D editor;
- make `world_*` default-profile tools;
- allow `present()` to upgrade a lower-layer `not_verified` into success.

## 3. Step D Contract

Step D consumes a Step C world envelope and produces a present-compatible packet.

Input shape:

```text
WorldToolEnvelope {
  schema: "agent_bridge.world_tool.v0",
  ok: bool,
  verified: bool,
  reason: string|null,
  endpoint: {...},
  request: {...},
  verify: {
    method: string,
    verified_to: string|null,
    evidence: {...}
  },
  host_response?: object|null
}
```

Output shape:

```text
WorldPresentPacket {
  schema: "agent_bridge.lswr.present_packet.v0",
  source_schema: "agent_bridge.world_tool.v0",
  world_tool: "world_query" | "world_patch" | "world_visibility_query",
  verdict: "verified" | "not_verified" | "blocked",
  title: string,
  summary: string,
  human_readable: {
    changed?: string[],
    visible?: string[],
    warnings?: string[],
    reason?: string|null
  },
  machine_payload: {
    request: object,
    verify: object,
    selected_entities: object[],
    patch_result?: object|null,
    source_reason: string|null
  },
  provenance: {
    commit?: string|null,
    adapter: "onsen",
    verified_to: string|null,
    verify_method: string,
    generated_at: string
  },
  ingestion: {
    allowed: false,
    reason: "step_d_expression_gate_not_accepted"
  }
}
```

The packet can be rendered by `present(kind="html" | "table", payload=packet, ...)`
or by a future thin `world_present` helper. The first Step D slice should prefer
manual or helper-level composition over adding a new runtime core.

## 4. Verdict Mapping

Step D must preserve the lower-layer truth.

| Step C state | Step D verdict | Human wording |
|---|---|---|
| `verified=true` | `verified` | The runtime verified this against the live render |
| `verified=false` + reason | `not_verified` | The runtime could not verify this result; show reason |
| host unreachable / timeout / malformed | `blocked` or `not_verified` | The world adapter could not provide evidence |
| invalid patch / non-loopback rejected | `blocked` | The operation was not safely attempted |

Rules:

- If Step C returns `verified=false`, Step D must not say "success" in the
  artifact title, summary, card color, or outcome sidecar.
- If Step C returns `reason`, Step D must display it and preserve it in payload.
- If Step C has `verified_to=null`, Step D must not invent a human-visible target.
- If raw host response is absent, Step D must still have enough reason/evidence
  from the stable envelope.

## 5. Human Artifact Requirements

The Step D artifact should answer five human questions:

1. What did the AI try to do?
2. What changed in the semantic world?
3. What did the live render verify?
4. What failed or could not be verified?
5. What can the human do next: accept, reject, inspect, retry, or branch later?

Minimum layout:

```text
Title: World patch verified / not verified / blocked
Status band: verdict + reason
Patch summary: op/entity/args + before/after
Visibility summary: screen_area, bounds_screen_area, occluded/readable if present
Verification: method, verified_to, evidence highlights
Next action: human review prompt
Machine payload: embedded #ab-payload / dual-encoded structure
```

The human artifact is allowed to be simple. The important part is fidelity.

## 6. Machine Payload Requirements

The packet must remain useful to agents without OCR or screenshot parsing.

Required machine fields:

- `schema`;
- `source_schema`;
- `world_tool`;
- `verdict`;
- `reason`;
- `verify.method`;
- `verify.verified_to`;
- `verify.evidence.host_reason`;
- selected entity IDs;
- selected screen metrics;
- raw host response presence flag;
- `ingestion.allowed=false` until D-gate.

The payload should omit or summarize heavy raw host data by default, but never
drop the top-level reason or verification method.

## 7. Relationship To `present_outcomes`

The current output lane can already create verified outcome sidecars. For LSWR,
that is useful but dangerous if used too early.

Step D policy:

- `present()` artifacts may be generated for human review.
- `present_outcomes` may observe those artifacts as output-lane audit records.
- `present_outcomes_ingest` must stay manual / dry-run for LSWR world results
  until Step D passes its expression gate.
- No Step D artifact should set or imply `ingestion.allowed=true` in v0.
- A later Step E may decide which LSWR outcomes are eligible for #94 ingestion;
  see [Step E Outcome Ingestion Policy](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E_OUTCOME_INGESTION_2026_06_08.md).

This keeps expression and learning separate:

```text
world result -> present packet -> human review -> D-gate accepted
  -> later #94 ingestion decision
```

## 8. Suggested Step D Slices

### D0 - Design sign-off

Accept this spec or revise it before implementation.

Decision points:

- Use manual `present()` composition first, or add a helper tool later?
- Which artifact kind should be first: HTML card or table?
- Is human accept/reject in scope now, or D2?
- Which LSWR world result examples are canonical for acceptance?

### D1 - Static Review Packet

Create a presentable static artifact from one saved Step C envelope.

Scope:

- no live Onsen launch;
- no new MCP tool required;
- construct `WorldPresentPacket`;
- render via existing `present()` in an all-profile validation surface;
- verify the artifact preserves `verified`, `not_verified`, and `blocked`.

### D2 - Human Review Action

Add accept/reject/comment as a human action surface.

Preferred path:

- reuse `present_await_decision` or an equivalent review card;
- keep the decision separate from the original Step C verification;
- record "human accepted this presentation" rather than "world claim became
  verified because human clicked accept."

### D3 - Outcome Gating

Define when a Step D artifact can enter #94-style verified outcome flow.

Minimum gate:

- source Step C result was `verified=true`;
- Step D expression fidelity passed;
- human review, if required, was positive;
- no lower-layer reason was lost;
- packet still includes machine-readable provenance.

D3 is design-only unless the owner explicitly opens ingestion work.

## 9. Acceptance Gates

### D1. Verdict fidelity

Given three Step C envelopes:

- `verified=true`;
- `verified=false reason=pixel_coverage_zero`;
- `reason=world_host_unreachable`;

the presented artifact must preserve and visibly distinguish all three.

### D2. Machine payload fidelity

An agent parsing the artifact payload once must recover the same verdict,
reason, `verify.method`, and `verified_to` as the source packet.

### D3. No success laundering

No lower-layer `not_verified` or `blocked` result can become a successful-looking
title, status, outcome, or ingestion-eligible record.

### D4. Present compatibility

The artifact should satisfy existing `present()` checks for render and payload
structure. Any `present()` self-verification failure is a Step D failure.

### D5. #94 restraint

No automatic memory/training ingestion happens during Step D. If a sidecar is
produced by the output lane, LSWR ingestion still remains disallowed by policy
until D3/D-gate accepts it.

### D6. Human readability

The human can tell:

- what was attempted;
- what was verified;
- what was not verified;
- why it failed or blocked;
- what the next review action means.

## 10. Canonical Test Fixtures

Step D should use fixtures from the accepted Step C evidence rather than a live
GUI by default.

The first D1 fixture set is documented in
[Step D D1 Review Packet Fixtures](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_D_D1_REVIEW_PACKET_FIXTURES_2026_06_06.md)
with JSON data at
[fixtures/lswr-step-d-d1-review-packets.json](fixtures/lswr-step-d-d1-review-packets.json).

Minimum fixtures:

1. **Verified visibility**:
   - `verified=true`;
   - `verified_to="onsen_live_root_viewport"`;
   - `verify.method="live_viewport_pixel_coverage"`.
2. **Alpha-zero not verified**:
   - `verified=false`;
   - `reason="pixel_coverage_zero"`;
   - `verify.evidence.host_reason="pixel_coverage_zero"`;
   - `include_raw=false` compatible.
3. **Host unreachable**:
   - `verified=false`;
   - `reason="world_host_unreachable"`;
   - `verified_to=null`.
4. **Blocked boundary**:
   - non-loopback rejected or invalid patch;
   - `blocked` presentation verdict.

Live Onsen verification is not required for D1. It becomes useful only if D2/D3
claim a live human review workflow.

## 11. Open Questions

These should be answered at D0 sign-off:

1. Should the first implementation be a doc + sample artifact only, or a helper
   that converts Step C envelopes into packets?
2. Should Step D use `present(kind="html")` first for readability, or
   `present(kind="table")` first for structured comparison?
3. Should human accept/reject be part of Step D, or should Step D stop at honest
   presentation and leave review actions for Step E?
4. Should LSWR world packets be allowed into `present_outcomes` but blocked from
   `present_outcomes_ingest`, or should Step D use a non-ingesting dry-run
   surface until accepted?

## 12. Recommended Decision

Recommended D0 decision:

- D1 should be **static HTML review packet first**.
- It should use saved Step C envelopes, not a live Onsen session.
- It should call existing `present()` only in a validation surface, with no new
  default-profile tools.
- Human accept/reject should be D2.
- #94 ingestion should be D3 or later.

This keeps the next slice small and directly tests the original thesis:

> the AI can not only change and perceive the world, but can express what
> happened to a human without losing the truth of the world verification.
