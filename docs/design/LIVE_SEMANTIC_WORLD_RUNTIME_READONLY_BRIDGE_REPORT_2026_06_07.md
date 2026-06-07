# Live Semantic World Runtime Read-Only Bridge Report

Date: 2026-06-07

Status: P27 draft, shared human/agent report surface

## Purpose

P26 made `ReadOnlyBridgeSnapshot` easier for agents and UI code to consume by
projecting it into `ReadOnlyBridgeConsumerSummary`. P27 adds the next expression
layer: a stable text report that humans and agents can read without opening raw
JSON.

The report is intentionally generated from the P26 summary rather than from a
runtime. It is a read-only presentation surface, not a new authority surface.

## Artifacts

- Report renderer:
  `crates/bridge/src/lswr_snapshot_report.rs`
- Report example:
  `cargo run -p ab-bridge --example lswr_readonly_bridge_report -- crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json`
- Detailed report fixture:
  `crates/bridge/tests/fixtures/lswr_readonly_bridge_report_detailed_v0.md`
- Counts-only report fixture:
  `crates/bridge/tests/fixtures/lswr_readonly_bridge_report_counts_only_v0.md`
- Focused test:
  `cargo test -p ab-bridge --test lswr_readonly_bridge_report -- --nocapture`

## Contract

The report identifies itself with:

`agent_bridge.lswr.readonly_bridge_report.v0`

It renders:

- source summary/projection schemas
- source snapshot hash
- readback mode
- read-only safety flags
- counts
- query surfaces
- verification outcome counts
- verified/not verified/blocked sections
- human feedback section
- rollback section
- reader guidance

When detailed snapshot data is unavailable, the report stays useful by showing
counts, query surfaces, and `unknown` outcome counts. It does not fabricate
per-record verification, feedback, or rollback details.

## Boundaries

This slice does not:

- register MCP tools
- edit `crates/bridge/src/mcp_tools.rs`
- launch or patch a runtime
- read arbitrary host files through MCP
- execute rollback
- convert human feedback into verification truth
- claim Step D, #92 present wiring, #94 ingestion, or Semantic System Bus work

This report is the shared expression layer between AI and human review. It makes
the semantic world state legible while preserving the authority boundaries from
P24-P26.
