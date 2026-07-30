# ADR: CLI Composition Root Governance S5-J — BioCortex Authorization Decision Packet

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

`crates/bridge/src/main.rs` owns
`run_biocortex_retrieval_opt_in_authorization_decision_packet`. The adapter
currently combines two distinct responsibilities:

1. composition-root custody of two authorization JSON inputs, including file
   reads, exact error messages, deserialization, and option assembly; and
2. a pure call to the existing authorization-decision packet planner followed
   by deterministic JSON or text rendering.

The packet can report that an opt-in experiment may be implemented, so its
semantics are authority-sensitive. The existing planner is nevertheless
read-only: it does not write approval, approve a runtime adapter, permit default
retrieval influence, run BioCortex, call memory search, or change retrieval
order.

## Decision

Move only the pure planner-and-renderer responsibility into the private
`cli::biocortex` module.

The new private adapter receives a fully populated
`BioCortexRetrievalOptInAuthorizationDecisionPacketOptions` and `as_json`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch arm;
- both authorization input paths and their ordered file reads;
- the exact read and parse error messages;
- JSON deserialization;
- complete option assembly;
- all post-implementation review, runtime influence, store, readiness,
  transition, deployment, and reconnect paths.

The planner in `biocortex_shadow.rs` is unchanged.

## Alternatives Considered

### Keep the mixed adapter in `main.rs`

This avoids a diff but continues the composition-root ownership violation and
leaves deterministic rendering coupled to filesystem custody.

### Move the whole adapter, including file I/O

This removes more lines but broadens `cli::biocortex` into input custody and
makes the authorization-sensitive boundary harder to audit.

### Move the Clap schema or authorization planner

This is unnecessary for the current unit and would expand the blast radius
beyond behavior-preserving CLI composition governance.

## Accepted Trade-offs

- `main.rs` remains responsible for repetitive input handling.
- The private module receives an authority-sensitive packet type.
- The line-count reduction is intentionally smaller than a whole-command move.

These costs preserve explicit custody and keep the extraction reversible.

## Verification Contract

Before implementation:

- add an ownership assertion and observe a RED failure because
  `cli::biocortex` does not yet own the adapter;
- capture current-main help, valid/blocked text and JSON, missing-file, and
  malformed-file behavior.

Before landing:

- pass the ownership test;
- pass focused authorization-decision schema, boundary, and privacy tests;
- pass `cli::biocortex` renderer tests;
- pass `cargo check --locked --offline -p ab-bridge --all-targets`;
- build a fresh candidate binary;
- prove baseline/candidate CLI output and exit-code equivalence;
- verify privacy sentinels remain absent;
- re-check current-main ancestry and both remotes.

## Non-goals

- changing authorization policy or planner semantics;
- granting runtime, production, default-order, hybrid, or semantic influence;
- connecting ordering behavior;
- changing stores, memory, network, or deployment state;
- deploying or reconnecting any client.
