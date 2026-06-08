# Live Semantic World Runtime Read-Only Bridge Display Model

Status: P30 draft, read-only bridge continuation.

## Purpose

P30 turns the P28 report packet and P29 acceptance matrix into a UI and agent friendly display model.

The display model is not a runtime surface. It is a deterministic read-only projection that lets a wrapper render status, safety, counters, gates, readback groups, guidance, and the existing Markdown report without duplicating packet and matrix interpretation logic.

## Schema

The display model schema is `agent_bridge.lswr.readonly_bridge_display_model.v0`.

Top-level fields:

- `schema`
- `packet_schema`
- `acceptance_schema`
- `snapshot_sha256`
- `title`
- `status`
- `safety`
- `badges`
- `metrics`
- `gate_rows`
- `readback_groups`
- `guidance`
- `report_markdown`

## Display Semantics

`status` maps acceptance state to a compact label and tone:

- `accepted` becomes `Ready for read-only display` with `success`.
- `needs_review` becomes `Needs review` with `warning`.
- required-gate failure or packet/matrix mismatch becomes `Rejected` with `danger`.

`safety.wrapper_ready` is true only when:

- packet and matrix snapshot identity match
- acceptance verdict is `accepted`
- packet read-only confirmation is true

`badges` expose compact routing facts such as overall verdict, wrapper readiness, matrix consistency, readback mode, read-only confirmation, and gate pass ratio.

`metrics` expose counts and outcome totals as strings so a UI can render them without schema-specific number formatting.

`readback_groups` group verified, not-verified, blocked, feedback, and rollback records into display rows.

## Boundaries

P30 remains outside runtime and MCP exposure:

- no `mcp_tools.rs` or registry changes
- no live runtime or GUI launch
- no arbitrary host read surface beyond explicit example input
- no world mutation, patch, action, or invoke affordance
- no Step D, #92 present wiring, or #94 ingestion

## Usage

The example accepts an explicit P28 report packet path, builds the P29 acceptance matrix internally, then prints the display model:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_display_model -- crates/bridge/tests/fixtures/lswr_readonly_bridge_report_packet_v0.json
```

This keeps presentation readiness separate from MCP or UI exposure. A later wrapper can consume the display model as a stable payload after a separate profile-gated exposure change.
