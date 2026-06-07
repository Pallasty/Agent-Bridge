# Live Semantic World Runtime Read-Only Bridge Acceptance Matrix

Status: P29 draft, read-only bridge continuation.

## Purpose

P29 adds a read-only acceptance matrix over the P28 report packet. Its job is to answer one narrow question before any UI, agent, daemon, or MCP wrapper consumes the packet:

Can this packet be treated as a safe read-only bridge output?

The matrix is not a runtime verifier. It is a deterministic contract check over an already-built packet.

## Schema

The acceptance matrix schema is `agent_bridge.lswr.readonly_bridge_acceptance_matrix.v0`.

Top-level fields:

- `schema`
- `packet_schema`
- `snapshot_sha256`
- `overall_verdict`
- `gates`
- `guidance`

Gate verdicts are string values:

- `passed`
- `warning`
- `failed`

Overall verdicts are:

- `accepted`
- `needs_review`
- `rejected`

## Gates

The initial matrix includes seven gates:

- `schema_chain`: packet, summary, report, projection, and snapshot hash schema chain is internally consistent.
- `packet_summary_consistency`: packet top-level fields mirror the nested summary.
- `read_only_safety`: read-only, no MCP registration, no mutation surface, no patch/action/invoke affordance.
- `query_surface_contract`: expected query-only surfaces are present and no mutation-like query surface appears.
- `report_markdown_consistency`: embedded Markdown exactly matches a fresh render from the packet summary.
- `detailed_readback`: detailed snapshot outcome counts are present and match the item lists.
- `feedback_verdict_separation`: human feedback stays feedback and does not rewrite verification verdicts.

Required wrapper gates reject the packet when they fail. Non-required detailed readback can produce `needs_review` for counts-only packets instead of rejection.

## Boundaries

P29 remains outside the runtime and MCP surfaces:

- no `mcp_tools.rs` or registry changes
- no live runtime or GUI launch
- no arbitrary host read surface beyond explicit example input
- no world mutation, patch, action, or invoke affordance
- no Step D, #92 present wiring, or #94 ingestion

## Usage

The example accepts an explicit P28 report packet JSON path and prints the matrix:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_acceptance_matrix -- crates/bridge/tests/fixtures/lswr_readonly_bridge_report_packet_v0.json
```

This keeps wrapper readiness separate from wrapper exposure. A later MCP or UI task can consume the matrix as evidence without duplicating acceptance logic.
