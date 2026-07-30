# ADR: CLI Composition Root Governance S5-N — BioCortex Runtime Readiness Packet

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

The next functions after S5-M include store trials and batch diagnostics that
open `state.db` or run live side-signal queries. Moving those executors would
transfer runtime and store custody rather than merely reduce composition-root
rendering.

`run_biocortex_retrieval_opt_in_runtime_readiness_packet` has a narrower split:

1. `main.rs` reads an authorized decision packet, store-trial evidence, and
   batch diagnostics in a fixed order, with exact errors and deserialization;
2. a pure synchronous planner evaluates the already-produced evidence and
   deterministically renders JSON or text.

The resulting packet may report that controlled explicit-opt-in FTS calls can
be accepted. It does not grant a runtime transition or execute retrieval
influence.

## Decision

Move only the populated-options planner-and-renderer adapter into private
`cli::biocortex`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch;
- ordered reads of decision packet, store trial, then batch diagnostics;
- every exact read and parse error;
- deserialization and complete
  `BioCortexRetrievalOptInRuntimeReadinessPacketOptions` assembly;
- all environment, store, runtime, transition, deployment, and reconnect
  paths.

The planner in `biocortex_shadow.rs` remains unchanged.

## Alternatives

### Keep the mixed adapter in `main.rs`

Avoids a diff, but leaves deterministic rendering coupled to evidence-file
custody.

### Extract the store and batch executors first

Would reduce more lines, but moves database access and live-query authority
into a renderer-oriented module.

### Extract the runtime transition gate in the same unit

Although its planner is pure, it is a separate authority decision with
operator-disable environment semantics and needs an independent gate.

## Trade-offs

- Three repetitive evidence reads remain in `main.rs`.
- The private module receives options capable of reporting positive controlled
  readiness.
- Line reduction is intentionally smaller than moving the entire runtime
  family.

These costs preserve input precedence, runtime authority, and reversibility.

## Verification Contract

- Observe the exact ownership RED before production changes.
- Pass ownership and three-input custody assertions.
- Pass focused runtime-readiness planner, MCP schema, and privacy tests.
- Pass repository pre-commit and a fresh locked/offline all-target check.
- Compare baseline and candidate help, ready/blocked text and JSON,
  missing/malformed inputs, input-error precedence, exit codes, stdout/stderr,
  and privacy sentinels.
- Reconcile concurrent main changes before dual-remote landing.

## Non-goals

- moving `state.db` or store lifecycle ownership;
- running store trials, batch diagnostics, BioCortex, or `memory_search`;
- granting or executing a runtime transition;
- changing retrieval order, schemas, MCP exposure, or privacy redaction;
- changing environment/operator-disable semantics;
- deployment or client reconnect.
