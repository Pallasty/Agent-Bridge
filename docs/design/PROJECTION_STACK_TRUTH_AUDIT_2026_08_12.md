# Projection Stack Truth Audit

**Date:** 2026-08-12  
**Gate:** Gate 0, read-only truth audit  
**Runtime admission:** unchanged

## Purpose

This audit separates current source, installed-binary, and connected-MCP facts
before adding a generative visual provider or another engine adapter. It does
not register tools, enable feature flags, launch a world host, or admit a
projection provider.

## Evidence Snapshot

| Boundary | Observed identity | Result |
| --- | --- | --- |
| local and both tracked remotes | `99408b8b` | synchronized; clean `master` |
| installed wrapper target | `6a4c824d50b8` | ancestor of current `master`, but not current HEAD |
| connected MCP process | `3db1c7e52ed8` | ancestor of current `master`; stale relative to installed binary and HEAD |
| connected MCP profile | `codex-lean` / `essential` | 54 tools; Niche projection tools intentionally hidden |
| embodiment P4 capability | `compiled=false`, `mcp_opted_in=false` | not available in the connected runtime |

The connected process therefore cannot be used as proof of current source or
installed-binary behavior. A later deployment gate must rebuild from a named
SHA, install through the project deployment path, restart MCP, and verify the
fresh process separately.

## Capability Classification

| Capability | Source state | Connected runtime state | Classification |
| --- | --- | --- | --- |
| `present` artifact sink | implemented; Niche registry tier | not exposed by Essential | source-live, profile-hidden |
| `present_replay` hash-chain audit | implemented; Niche registry tier | not exposed by Essential | source-live, profile-hidden |
| `present_dashboard` and outcome projections | implemented; Niche registry tier | not exposed by Essential | source-live, profile-hidden |
| `world_query` | implemented against the configured world host endpoint | not exposed by Essential | source-live, host-dependent |
| `world_patch` | implemented, with verified/blocked/not-verified separation | not exposed by Essential | source-live, host-dependent, mutating |
| `world_visibility_query` | implemented with structured render-grounded evidence | not exposed by Essential | source-live, host-dependent |
| `world_present` | implemented as a no-laundering expression wrapper | not exposed by Essential | source-live, profile-hidden |
| LSWR Rust world core and ledger | implemented with fixtures, tests, and staged gates | not a standalone MCP capability | source-live substrate |
| embodiment `ProjectionPlan` | implemented behind `embodiment-runtime-p4` | explicitly not compiled in connected MCP | source-only for this runtime |
| ABot-World provider | no adapter or registration found | unavailable | design-only |
| UE5 provider | no adapter found | unavailable | absent |
| provider-neutral comparison receipt | no shared contract found | unavailable | design gap |

## Important Semantic Collision

`agent_bridge.projection_plan.v0` already means an owner-confirmed, bounded plan
for executing an operation against a body. It requires an approved authority
decision, an exact world revision, owner confirmation, and re-observation. It is
an action-safety contract, not a media-generation or renderer-selection
contract.

The visual projection stack must not overload that schema or weaken its
authority semantics. A separate request envelope is required.

## Existing Assets To Reuse

1. `present` remains the human-facing artifact transport and gallery.
2. `present_replay` remains the artifact replay and tamper/drift audit.
3. LSWR world envelopes remain the structured world/action/evidence substrate.
4. `world_present` remains the no-laundering conversion into human-readable
   review packets.
5. The embodiment `ProjectionPlan` remains reserved for authorized effects on
   bodies.

## Gate 0 Verdict

`TRUTH_MAPPED_RUNTIME_UNCHANGED`

The next admissible step is a design-only provider-neutral contract. Runtime
implementation, provider smoke tests, MCP registration, deployment, and claims
of readiness remain out of scope.
