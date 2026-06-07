# Semantic System Bus LSWR Action Result Pilot

**Status:** SSB-3 action/result pilot  
**Date:** 2026-06-07  
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

This pilot makes LSWR the first action-bearing Semantic System Bus surface.

SSB-2 proved a read-only Palace graph observation envelope. SSB-3 adds a
normalized `action_result` block to the mature LSWR world tool family while
preserving the existing `agent_bridge.world_tool.v0` payload shape.

The loop now covered by concrete Agent-Bridge surfaces is:

```text
Semantic Object -> Affordance/Action -> Action Result -> Verification -> Presentation
```

## 1. Touched Tools

The wrapper is emitted by:

```text
world_query
world_visibility_query
world_patch
```

`world_present` does not re-verify the result. It preserves
`envelope.action_result` inside `packet.machine_payload.action_result` and
continues to derive human-facing verdicts from the original world tool envelope:

```text
verified
reason
verify.verified_to
verify.evidence.host_reason
```

This keeps Step D's no-laundering rule intact.

## 2. Action Result Shape

The normalized block uses:

```text
agent_bridge.semantic_bus.action_result.v0
```

Current fields:

```text
schema
source_schema
adapter
world_tool
action_type
action_id
request_id
subject_id
event_ids
verdict
reason
verified_to
verification_method
recover
raw_available
```

Example:

```json
{
  "schema": "agent_bridge.semantic_bus.action_result.v0",
  "source_schema": "agent_bridge.world_tool.v0",
  "adapter": "lswr.onsen",
  "world_tool": "world_patch",
  "action_type": "world.patch",
  "action_id": "lswr:world_patch:ssb3-patch:result",
  "request_id": "ssb3-patch",
  "subject_id": "lswr:onsen:entity:bath",
  "event_ids": ["evt-lswr-world_patch-ssb3-patch"],
  "verdict": "verified",
  "reason": null,
  "verified_to": "onsen_live_root_viewport",
  "verification_method": "live_viewport_pixel_coverage",
  "recover": "proceed",
  "raw_available": true
}
```

## 3. Verdict Mapping

The wrapper deliberately keeps result truth narrow:

| Condition | `action_result.verdict` | `recover` |
| --- | --- | --- |
| `verified=true` | `verified` | `proceed` |
| blocked safety/patch reason | `blocked` | `replan` |
| other unverified result | `not_verified` | `inspect_host_or_visibility_evidence` |

Blocked reasons currently recognized:

```text
world_host_non_loopback_rejected
world_patch_invalid
world_patch_blocked
```

The wrapper only sets `verified_to=onsen_live_root_viewport` when the lower
world tool envelope is verified. Failed or blocked host interactions keep
`verified_to=null`.

## 4. Compatibility Rules

- Existing top-level fields remain: `schema`, `ok`, `verified`, `reason`,
  `endpoint`, `request`, `verify`, and optional `host_response`.
- `include_raw=false` still removes `host_response`, but keeps `action_result`.
- `raw_available=true` means a host response existed before raw stripping.
- `world_present` can infer the source world tool from
  `action_result.world_tool`, which avoids confusing `world_query` with explicit
  `world_visibility_query` when both use `world.visibility.query` requests.

## 5. Boundaries

- No durable event-spine persistence yet.
- No memory ingestion.
- No screenshot or OCR dependency.
- No cross-platform desktop action wrapper yet.
- No claim that LSWR semantics generalize to every app; this is a pilot for the
  schema contract.

## 6. Next Slice

After SSB-3, the next implementation slice should be SSB-4:

```text
Linux-first adapter conformance
```

Reason:

- Palace now covers read-only observation.
- LSWR now covers action/result/no-laundering.
- The next useful proof is adapter conformance for desktop semantic state,
  verification, and OCR fallback surfaces without broad host mutation.
