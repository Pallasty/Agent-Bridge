# ab-world-core

`ab-world-core` is the portable Live Semantic World Runtime model. It is
intentionally independent of Agent-Bridge MCP tools, browser adapters, renderer
hosts, storage, and presentation review cards.

Use this crate when an adapter needs to represent:

- AI or human actions against a semantic world;
- runtime events produced by applying those actions;
- verification evidence that can be read without screenshots as the primary
  perception path;
- human feedback that does not rewrite lower-layer verification truth;
- rollback groups and before/after state snapshots.

## Core Records

The root module re-exports the public API:

```rust
use ab_world_core::{
    Action, AdapterEvidence, AuthorityMode, Event, EventProvenance, Feedback,
    Participant, RollbackRecord, TargetRef, Verdict, Verification, WorldLedger,
};
```

The common adapter flow is:

1. Build a `Participant` for the AI, human, runtime, or adapter.
2. Build an `Action` with semantic `target_refs`, `expected_effect`, and an
   optional `rollback_group`.
3. Build a runtime `Event` that references the action, entities, rollback group,
   and adapter provenance.
4. Attach a `Verification` when the event claims a grounded result.
5. Append human accept/reject as separate event or feedback records; do not use
   human acceptance to mutate the original runtime verification.
6. Register a `RollbackRecord` when a change has a reversible before/after
   snapshot.

See `examples/basic_ledger.rs` for a complete executable example.

## Verification Invariants

`Verification::new` enforces the current truth boundary:

- `Verdict::Verified` requires `verified_to`.
- `Verdict::NotVerified` and `Verdict::Blocked` require a stable `reason`.
- `Verdict::NotVerified` and `Verdict::Blocked` must not set `verified_to`.

This keeps an adapter from laundering a failed or blocked projection into a
successful entity-level truth claim.

Human review has its own boundary. A `human.accept` or `human.reject` event can
record whether the human accepted a presentation, branch, or proposed direction,
but `WorldLedger::append_event` rejects human decision payloads that set
`changes_world_verdict=true`.

## Query Surface

The in-memory ledger is deliberately small. It can currently read back:

- all events;
- all verification records;
- all feedback records;
- rollback groups;
- one event by event id;
- events by event type;
- events by entity, action, rollback group, or participant;
- a neutral `world.events.query` envelope over matching event records;
- verification records by verdict;
- verification evidence by action id;
- feedback by source event or action;
- rollback records by action;
- a neutral `world.evidence.query` envelope over matching events and
  verification records.

This is enough for the P8 web prototype fixture and the first adapter-facing API
examples. More query helpers should be added only when a concrete adapter or
review surface needs them.

`EventQuery` applies all supplied filters together. It can filter by event id,
related event id, event type, world id, branch id, entity id, action id,
participant id, rollback group, adapter, and embedded verification verdict. The
response carries matched events and summary counts without binding the query to
MCP, storage, streaming, or a renderer.

`EvidenceQuery` applies all supplied filters together. It can filter by event
id, action id, entity id, participant id, rollback group, verdict, method, and
adapter kind. The response carries the matched events, matched verification
records, and summary counts without binding the query to MCP, storage, or a
specific renderer.

## Fixture Pressure Tests

The integration fixtures intentionally cover more than one presentation shape:

- `tests/fixtures/p8_world_export.json` maps the web prototype into the core
  ledger without laundering `not_verified` or `blocked` truth.
- `tests/fixtures/nexus_causal_seed.json` maps a non-visual causal event chain
  into the same ledger using event-to-event refs and Nexus evidence payloads,
  without requiring visual fields such as `screen_area` or `pixel_coverage`.

The P8 fixture carries a copy of
`prototypes/lswr-web-prototype/contract/p8_world_core_contract.json`, so the
web export script and Rust mapping test assert the same counts, paths, and
truth-boundary expectations.

## Local Verification

From the workspace root:

```sh
cargo test -p ab-world-core -- --nocapture
cargo check -p ab-world-core --all-targets
cargo clippy -p ab-world-core --all-targets -- -D warnings
cargo run -p ab-world-core --example basic_ledger
```

These checks do not start Agent-Bridge, open Step D, register MCP tools, ingest
verified outcomes, or launch a renderer.
