# Live Semantic World Runtime - Core Query Acceptance

Date: 2026-06-07

## Status

Ready for acceptance as a core-only closure target after P17-P21.

This note documents what the `ab-world-core` query surface now proves before
any Agent-Bridge MCP, renderer, storage, streaming, or Semantic System Bus
runtime exposure.

## Acceptance Claim

`ab-world-core` can represent and read back the smallest useful semantic loop:

1. an AI or human `Action` intent;
2. a runtime `Event` produced by applying that action;
3. grounded `Verification` evidence attached to the result;
4. human `Feedback` that does not rewrite lower-layer truth;
5. a `RollbackRecord` linking the action to reversible before/after state.

Each record class has a neutral query envelope:

| Surface | Schema | Purpose |
| --- | --- | --- |
| `world.actions.query` | `agent_bridge.lswr.action_query.v0` | Read intended action, source, targets, expected effect, rollback link |
| `world.events.query` | `agent_bridge.lswr.event_query.v0` | Read runtime event/result stream |
| `world.evidence.query` | `agent_bridge.lswr.evidence_query.v0` | Read verification events and standalone evidence records |
| `world.feedback.query` | `agent_bridge.lswr.feedback_query.v0` | Read human or adapter feedback without laundering truth |
| `world.rollback.query` | `agent_bridge.lswr.rollback_query.v0` | Read reversible before/after state snapshots |

The acceptance test is:

```sh
cargo test -p ab-world-core --test core_query_closure -- --nocapture
```

It builds one semantic move and proves the full query closure:

```text
Action -> Event -> Verification -> Feedback -> RollbackRecord
```

The verification evidence is semantic-state evidence. It intentionally does not
depend on screenshots, `pixel_coverage`, or a live renderer. Visual adapters can
still add visual evidence later, but core acceptance does not require pixels as
the primary perception path.

## Boundaries

This acceptance package does not:

- edit `crates/bridge`;
- register MCP tools;
- expose Step D, #92 present wiring, or #94 verified-outcome ingestion;
- add persistence, indexing, streaming, or storage-backed queries;
- normalize Semantic System Bus runtime output.

Those are follow-on lanes. The point here is only to prove that a future adapter
has a portable Rust core target it can write into and query back.

## Evidence

Current supporting tests:

- `crates/world-core/tests/core_query_closure.rs`
- `crates/world-core/tests/p8_fixture_mapping.rs`
- `crates/world-core/tests/nexus_causal_fixture.rs`
- `crates/world-core/src/tests.rs`

Current local verification set:

```sh
cargo test -p ab-world-core --all-targets -- --nocapture
cargo check -p ab-world-core --all-targets
cargo clippy -p ab-world-core --all-targets -- -D warnings
cargo run -p ab-world-core --example basic_ledger
cargo fmt -p ab-world-core -- --check
cargo tree -p ab-world-core --edges normal
git diff --check
```

## Next Decision

After this closure is accepted, the next lane should choose one of two paths:

- keep strengthening core-only contracts, such as persistence-neutral ordering
  or stable export/import envelopes;
- deliberately leave core and open a separate bridge/MCP exposure lane.

Do not mix those paths in the same worktree.
