# Live Semantic World Runtime Read-Only Bridge Prep

Date: 2026-06-07

Status: P24 draft, collision-safe bridge precursor

## Context

The `ab-world-core` crate now has a portable ledger snapshot contract:

- `WorldLedgerSnapshot`
- `WorldLedger::to_snapshot()`
- `WorldLedger::from_snapshot(...)`
- neutral query envelopes for actions, events, evidence, feedback, and rollback records

The next useful bridge step is to expose this core state to Agent-Bridge without
turning it into a mutation or runtime invocation surface. At the same time,
thread #107 is working on Semantic System Bus normalization in
`crates/bridge/src/mcp_tools.rs`, so this slice deliberately avoids MCP registry
wiring.

## Scope

This slice adds `crates/bridge/src/lswr_snapshot_bridge.rs` as a bridge-side
read-only projection over `WorldLedgerSnapshot`.

The projection returns:

- bridge projection schema: `agent_bridge.lswr.readonly_bridge_snapshot.v0`
- source snapshot schema: `agent_bridge.lswr.ledger_snapshot.v0`
- stable `sha256:` hash of the source snapshot JSON
- read-only affordances
- counts for actions, events, verifications, feedback, and rollback records
- the five neutral query surface names and schemas
- optional raw snapshot embedding when explicitly requested

The projection validates the snapshot by importing it through
`WorldLedger::from_snapshot(...)` before reporting counts or query surfaces.

## Non-Goals

This slice does not:

- register a new MCP tool
- touch `crates/bridge/src/mcp_tools.rs`
- add a write, patch, invoke, or action execution surface
- claim Step D, #92 present wiring, #94 ingestion, or Semantic System Bus work
- launch a live runtime or GUI verifier

## Acceptance

Focused tests cover:

- valid ledger snapshots are projected with read-only affordances
- raw snapshots are omitted by default and included only when requested
- invalid core snapshot imports are rejected instead of normalized

Follow-up MCP registration should wait until the active #107
`mcp_tools.rs` line is closed or explicitly reassigns this bridge registration
work.
