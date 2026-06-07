# Live Semantic World Runtime Read-Only Bridge File IO

Date: 2026-06-07

Status: P25b draft, snapshot file import example

## Purpose

P25a made the read-only bridge projection replayable as a static JSON fixture.
P25b adds the input side: a raw `WorldLedgerSnapshot` fixture and an example
that reads the snapshot from disk before projecting it into the bridge readback
contract.

## Artifacts

- Raw snapshot fixture:
  `crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json`
- Projection fixture:
  `crates/bridge/tests/fixtures/lswr_readonly_bridge_projection_v0.json`
- File IO example:
  `cargo run -p ab-bridge --example lswr_readonly_bridge_project_snapshot -- crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json`
- Focused test:
  `cargo test -p ab-bridge --test lswr_readonly_bridge_file_io -- --nocapture`

## Contract

The file IO example:

- reads a `WorldLedgerSnapshot` JSON file
- deserializes it with `ab-world-core`
- validates it through `build_readonly_bridge_snapshot(...)`
- prints `agent_bridge.lswr.readonly_bridge_snapshot.v0`
- omits the raw snapshot by default
- includes the raw snapshot only with `--include-snapshot`

## Boundaries

This slice does not:

- register MCP tools
- touch `crates/bridge/src/mcp_tools.rs`
- launch or patch any runtime
- widen authority beyond read-only snapshot projection

The intent is to make eventual MCP registration mostly a transport wrapper
around a proven file/import/projection contract.
