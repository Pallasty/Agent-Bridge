# Live Semantic World Runtime Read-Only Bridge Fixture

Date: 2026-06-07

Status: P25a draft, replay fixture and example

## Purpose

P24 added a bridge-side read-only projection over `WorldLedgerSnapshot`. P25a
adds a stable JSON fixture and example so the projection can be inspected and
replayed before any MCP registration or runtime adapter wiring.

## Artifacts

- Fixture:
  `crates/bridge/tests/fixtures/lswr_readonly_bridge_projection_v0.json`
- Replay/generation example:
  `cargo run -p ab-bridge --example lswr_readonly_bridge_projection`
- Validation test:
  `cargo test -p ab-bridge --test lswr_readonly_bridge_fixture -- --nocapture`

## Fixture Contract

The fixture uses schema:

`agent_bridge.lswr.readonly_bridge_snapshot.v0`

It contains:

- source snapshot schema
- source snapshot `sha256:` hash
- read-only affordances
- counts for actions, events, verifications, feedback, and rollback records
- query surfaces for actions, events, evidence, feedback, and rollbacks

It intentionally omits raw `WorldLedgerSnapshot` by default. That keeps the
fixture compact and matches the intended readback behavior for an eventual MCP
tool.

## Boundaries

This slice does not:

- register MCP tools
- touch `crates/bridge/src/mcp_tools.rs`
- invoke or patch a live runtime
- claim Step D, #92 present wiring, or #94 ingestion

The fixture exists to make downstream bridge/adapter wiring reviewable before
introducing another runtime surface.
