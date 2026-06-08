# Live Semantic World Runtime - Ledger Snapshot Contract

Date: 2026-06-07

## Status

Ready for core-only acceptance after the query closure package.

This note defines the first portable export/import contract for
`ab-world-core`. It is deliberately below Agent-Bridge MCP, storage, streaming,
renderer, and Semantic System Bus runtime exposure.

## Contract

`WorldLedgerSnapshot` uses:

```text
agent_bridge.lswr.ledger_snapshot.v0
```

It carries the current in-memory core records:

- `actions`
- `events`
- `verifications`
- `feedback`
- `rollback_records`

`WorldLedger::to_snapshot()` exports the current ledger. Rollback records are
sorted by `rollback_group` before export so the snapshot does not expose the
internal `HashMap` iteration order.

`WorldLedger::from_snapshot(...)` imports a snapshot and validates existing core
invariants before accepting it:

- snapshot schema must match `agent_bridge.lswr.ledger_snapshot.v0`;
- duplicate action ids are rejected;
- verification truth-boundary rules still apply;
- human decision events cannot set `changes_world_verdict=true`;
- feedback cannot set `changes_world_verdict=true`;
- duplicate rollback groups are rejected.

The importer intentionally preserves event-embedded verification records and the
top-level verification list without re-appending embedded records. This keeps
snapshot round-trips stable while still validating both surfaces.

## Acceptance Test

```sh
cargo test -p ab-world-core --test ledger_snapshot -- --nocapture
```

The test builds the same semantic closure shape as the core query acceptance
lane, exports it, serializes it to JSON, imports it back, and reruns the neutral
query envelopes:

- `world.actions.query`
- `world.events.query`
- `world.evidence.query`
- `world.feedback.query`
- `world.rollback.query`

The imported ledger must produce matching query summaries. The test also proves
rollback export order is stable and that bad imports are rejected.

## Boundary

This is not an MCP tool, not a storage schema, and not a bridge exposure. It is
the transport precursor that lets a future read-only bridge lane expose the core
state without depending on private in-memory layout.

The next bridge/MCP lane should consume this contract rather than serializing
`WorldLedger` internals directly.
