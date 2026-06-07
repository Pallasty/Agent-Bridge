# Live Semantic World Runtime Read-Only Bridge Consumer Packet

Date: 2026-06-07

Status: P26 draft, consumer-side readback contract

## Purpose

P24/P25 made `WorldLedgerSnapshot` visible as a bridge-side read-only
projection. P26 adds the next local contract: a consumer summary that UI,
agents, and reviewers can read without understanding every ledger field.

The new consumer summary answers:

- is this projection still read-only?
- are mutating affordances disabled?
- is detailed readback available or only counts/query surfaces?
- which actions are verified, not verified, or blocked?
- which human feedback entries exist, and did any attempt to change world
  verification truth?
- which rollback groups are described, without executing rollback?

## Artifacts

- Consumer module:
  `crates/bridge/src/lswr_snapshot_consumer.rs`
- Consumer fixture:
  `crates/bridge/tests/fixtures/lswr_readonly_bridge_consumer_summary_v0.json`
- Consumer tests:
  `cargo test -p ab-bridge --test lswr_readonly_bridge_consumer -- --nocapture`
- Consumer example:
  `cargo run -p ab-bridge --example lswr_readonly_bridge_consumer_summary -- crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json`

## Contract

The consumer summary uses schema:

`agent_bridge.lswr.readonly_bridge_consumer_summary.v0`

It accepts an existing `ReadOnlyBridgeSnapshot` and returns:

- source projection schema and snapshot hash
- `readback_mode`
- read-only safety flags
- high-level counts
- detailed outcome counts when the raw snapshot is embedded
- verification records grouped by verdict
- feedback records kept separate from verification
- rollback group references
- short guidance strings for readers

If a projection omits its raw snapshot, the consumer summary degrades to
`readback_mode=counts_only`. That mode is still safe for dashboards and board
reviews, but it cannot classify individual verification, feedback, or rollback
records.

## Boundaries

This slice does not:

- register MCP tools
- edit `crates/bridge/src/mcp_tools.rs`
- read arbitrary host files through MCP
- launch or patch a runtime
- execute rollback
- convert human feedback into verification truth
- claim Step D, #92 present wiring, #94 ingestion, or Semantic System Bus work

The consumer packet is intentionally a read-only adapter over an already-built
projection. It makes the current semantic world readable to humans and agents
without increasing authority.
