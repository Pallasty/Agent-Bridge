# Live Semantic World Runtime Read-Only Bridge MCP Exposure

Status: P34 draft, gated MCP exposure candidate.

## Purpose

P34 performs the explicit registry slice anticipated by the P31 descriptor, P32 dry-run, and P33 preflight report.

The new MCP tool is `lswr_readonly_bridge_display`. It is a read-only wrapper that consumes an explicit P28 `agent_bridge.lswr.readonly_bridge_report_packet.v0` JSON object and returns the derived P30 `agent_bridge.lswr.readonly_bridge_display_model.v0`.

## Tool Contract

Input:

- `report_packet`: the full report packet JSON object.

Rejected inputs:

- host paths
- packet paths
- snapshot paths
- files
- runtime URLs
- live runtime handles
- GUI captures
- screenshots or image inputs
- patch/action/invoke requests
- any unknown input key

Output:

- the P30 display model produced by `build_readonly_bridge_display_model_from_packet`.

The tool rejects a wrong packet schema before building the display model. Unsafe but structurally valid packets still return a display model with the existing danger status and `wrapper_ready=false`, so callers can read back the reason without the MCP layer laundering the packet into success.

## Profile Gate

`lswr_readonly_bridge_display` is registered as `Tier::Niche`.

Expected exposure:

- `AGENT_BRIDGE_TOOL_PROFILE=all`: visible
- standard/default profile: hidden
- `codex-essential`: hidden

It is not added to `CODEX_ESSENTIAL_DIRECT_EXTRAS` or any capability group.

## Safety Boundary

The tool does not:

- read files
- launch or query a live LSWR host
- capture screenshots
- inspect GUI state
- patch world state
- invoke actions
- write artifacts
- write memory graph edges

It only transforms a caller-provided packet object into the already-defined display model.

## Relationship To P31-P33

P31-P33 remain the pre-registry acceptance artifacts:

- P31 defines the intended wrapper descriptor.
- P32 proves the exposure request as a dry-run and rejects unsafe candidates.
- P33 packages the preflight report.

P34 applies that separate registry step while preserving the same constraints as tests: profile gate, explicit packet payload, schema contract, and no indirect source or mutation affordance.

## Verification

Focused verification should cover:

- MCP profile registration under `all` only
- schema exposing only `report_packet`
- successful P28 packet to P30 display model conversion
- refusal of path/live-runtime/GUI-capture inputs
- refusal of wrong packet schema
- preservation of unsafe packet verdicts in the display model
- existing P28-P33 regression tests
- `cargo check -p ab-bridge --all-targets`

