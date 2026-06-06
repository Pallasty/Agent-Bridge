# Live Semantic World Runtime - Step D D1 Review Packet Fixtures

**2026-06-06 - role: D1 fixture-backed expression proof**

Parent document:
- [Step D Present Spec](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_D_PRESENT_SPEC_2026_06_06.md)

Fixture data:
- [D1 JSON fixtures](fixtures/lswr-step-d-d1-review-packets.json)

## 0. Purpose

D1 is the first Step D slice. It should prove expression fidelity without
launching live Onsen or reopening Step C.

This document defines canonical source envelopes and expected present-packet
outputs for four cases:

1. verified visibility;
2. alpha-zero not verified;
3. host unreachable;
4. blocked boundary.

The same fixtures can later drive a small converter, a `present()` smoke, or a
human review card. For now they are a contract test vector.

## 1. D1 Scope

In scope:

- saved Step C-style envelopes;
- deterministic conversion into `agent_bridge.lswr.present_packet.v0`;
- human-readable summaries;
- machine-readable payloads;
- explicit `ingestion.allowed=false`;
- no live runtime dependency.

Out of scope:

- live Onsen host;
- new MCP tools;
- branch/rollback;
- human accept/reject;
- `present_outcomes_ingest`;
- #94 write path.

## 2. D1 Contract

Input:

```text
agent_bridge.world_tool.v0 envelope
```

Output:

```text
agent_bridge.lswr.present_packet.v0 packet
```

Required preservation:

| Source field | Packet field |
|---|---|
| `schema` | `source_schema` |
| tool name | `world_tool` |
| `verified` | `verdict` |
| `reason` | `reason` and `machine_payload.source_reason` |
| `verify.method` | `provenance.verify_method` and payload verify |
| `verify.verified_to` | `provenance.verified_to` and payload verify |
| `verify.evidence.host_reason` | payload verify evidence |
| host raw presence | `machine_payload.raw_host_response_present` |

## 3. Fixture Cases

### 3.1 Verified Visibility

Source meaning:

- world tool: `world_visibility_query`;
- entity: `bath`;
- result: verified against `onsen_live_root_viewport`;
- method: `live_viewport_pixel_coverage`;
- screen area is nonzero.

Expected Step D packet:

- `verdict="verified"`;
- human summary says the runtime verified the bath in the live viewport;
- payload preserves `verified_to="onsen_live_root_viewport"`;
- `ingestion.allowed=false`.

### 3.2 Alpha-Zero Not Verified

Source meaning:

- world tool: `world_visibility_query`;
- entity: `bath`;
- result: `verified=false`;
- reason: `pixel_coverage_zero`;
- raw host response is absent (`include_raw=false` compatible);
- the stable envelope still carries top-level `reason` and
  `verify.evidence.host_reason`.

Expected Step D packet:

- `verdict="not_verified"`;
- human summary clearly states the runtime could not verify visibility;
- reason is visible to the human;
- payload preserves `pixel_coverage_zero`;
- no wording implies success.

This is the critical Step C hotfix regression guard.

### 3.3 Host Unreachable

Source meaning:

- adapter did not provide live evidence;
- reason: `world_host_unreachable`;
- `verified_to=null`.

Expected Step D packet:

- `verdict="not_verified"`;
- human summary says the world adapter was unreachable;
- payload preserves `world_host_unreachable`;
- no render claim is made.

This is not a successful world result. It is an honest unavailable-world result.

### 3.4 Blocked Boundary

Source meaning:

- non-loopback host or unsafe endpoint rejected before attempting a live world
  operation;
- reason: `world_host_non_loopback_rejected`.

Expected Step D packet:

- `verdict="blocked"`;
- human summary says the operation was blocked for safety;
- payload preserves the reason;
- no world state or render verification is implied.

## 4. D1 Rendering Rules

When rendered through `present()`, each packet should produce a human artifact
with:

- a title that includes the verdict;
- a status band with reason when present;
- a short "what was attempted" section;
- a short "what the runtime verified" section;
- a short "what the human can do next" section;
- embedded machine payload parseable as JSON once.

The artifact must never use a green/success visual language for `not_verified`
or `blocked` packets.

## 5. D1 Acceptance

### D1-A. Fixture completeness

The fixture file contains all four canonical cases.

### D1-B. Verdict fidelity

The packet verdicts are:

```text
verified_visibility -> verified
alpha_zero_not_verified -> not_verified
host_unreachable -> not_verified
blocked_non_loopback -> blocked
```

### D1-C. Reason preservation

The packet preserves:

- `pixel_coverage_zero`;
- `world_host_unreachable`;
- `world_host_non_loopback_rejected`.

The reason must exist in human-readable text and machine payload.

### D1-D. Verification provenance

The packet preserves:

- `verify.method`;
- `verified_to`;
- measured evidence highlights;
- raw host response presence flag.

### D1-E. Ingestion restraint

Every packet has:

```json
{
  "ingestion": {
    "allowed": false,
    "reason": "step_d_expression_gate_not_accepted"
  }
}
```

### D1-F. No live dependency

D1 can be checked from saved fixtures only. Live Onsen is not required.

## 6. Recommended Next Step

After these fixtures are accepted, the next implementation slice can be either:

1. a small pure converter from Step C envelope JSON to Step D packet JSON; or
2. a static `present()` proof that renders these packets into review artifacts.

The safer order is converter first, render second.
