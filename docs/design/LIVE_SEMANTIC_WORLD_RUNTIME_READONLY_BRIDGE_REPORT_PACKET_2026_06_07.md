# Live Semantic World Runtime Read-Only Bridge Report Packet

Status: P28 draft, read-only bridge continuation.

## Purpose

P28 packages the P26 consumer summary and P27 Markdown report into one stable JSON packet:

- `summary`: structured readback for agents and tests.
- `report_markdown`: human-readable report text.
- top-level schemas, snapshot hash, readback mode, and safety flags for routing and display decisions.

This gives future UI, daemon, or MCP-facing wrappers a single payload to render or forward without re-reading arbitrary files or recomputing report text outside the bridge crate.

## Schema

The packet schema is `agent_bridge.lswr.readonly_bridge_report_packet.v0`.

Required top-level fields:

- `schema`
- `summary_schema`
- `report_schema`
- `projection_schema`
- `snapshot_sha256`
- `readback_mode`
- `read_only_confirmed`
- `safety`
- `summary`
- `report_markdown`

`safety` is repeated at the packet top level so consumers can reject unsafe or unexpectedly mutable payloads before traversing nested summary data.

## Boundaries

P28 remains intentionally narrow:

- no MCP registry or `mcp_tools.rs` changes
- no world mutation, patch, action, or invoke affordance
- no live runtime or GUI launch
- no arbitrary host file read surface
- no Step D, #92 present wiring, or #94 ingestion

The example reads an explicit ledger snapshot path supplied by the operator, builds the existing read-only projection and summary, and prints the report packet as pretty JSON.

## Verification

The packet fixture is generated from `lswr_ledger_snapshot_v0.json` through the existing read-only projection path. Tests assert that the packet:

- matches the generated fixture
- embeds the exact P27 detailed Markdown report
- preserves top-level schema and read-only safety flags
- keeps stable pretty JSON formatting
