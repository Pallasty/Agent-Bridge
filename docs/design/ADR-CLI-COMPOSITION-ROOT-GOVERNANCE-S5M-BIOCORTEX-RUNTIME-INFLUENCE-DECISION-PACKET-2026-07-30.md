# ADR: CLI Composition Root Governance S5-M — BioCortex Runtime-Influence Decision Packet

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

`run_biocortex_retrieval_opt_in_runtime_influence_decision_packet` currently
combines:

1. composition-root custody of a runtime-influence review request and a
   separate human decision, including ordered reads, exact errors,
   deserialization, and option assembly; and
2. a pure decision-packet planner call followed by deterministic JSON or text
   rendering.

The packet may authorize later implementation for explicitly opted-in FTS
calls. It does not itself run that implementation, call `memory_search`, run
BioCortex, connect ordering behavior, change retrieval order, write approval,
or permit default retrieval influence.

## Decision

Move only the pure planner-and-renderer responsibility into private
`cli::biocortex`.

The module receives a fully populated
`BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions` and `as_json`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch;
- ordered reads of the review request and then the human decision;
- every exact read and parse error;
- deserialization and complete option assembly;
- every downstream store, readiness, transition, deployment, and reconnect
  path.

The planner in `biocortex_shadow.rs` remains unchanged.

## Alternatives

### Keep the mixed adapter in `main.rs`

Lowest immediate diff, but deterministic rendering remains coupled to
authority-sensitive decision-file custody.

### Move both input reads into `cli::biocortex`

Removes more lines, but transfers authorization-input precedence and exact
error ownership into a renderer module.

### Extract the store trial in the same unit

Would combine a pure renderer boundary with store access and opt-in runtime
execution, expanding authority and verification scope.

## Trade-offs

- Both authority-sensitive input reads remain verbose in `main.rs`.
- The private module receives an options type capable of reporting a positive
  implementation authorization.
- The line reduction is intentionally limited.

These costs preserve authorization custody, error ordering, and reversibility.

## Verification Contract

- Add ownership and custody assertions first and observe the exact RED failure.
- Pass focused decision-packet boundary, schema, and privacy tests.
- Pass fresh-target compilation and touched-file formatting/diff checks.
- Build a fresh candidate binary.
- Compare baseline and candidate help, authorized/denied text and JSON,
  missing/malformed request, missing/malformed decision, exit codes,
  stdout/stderr, and privacy sentinels.
- Re-check current-main ancestry, concurrent changes, and both remotes before
  landing.

## Non-goals

- changing the human decision or planner authorization semantics;
- implementing or running authorized explicit-opt-in FTS influence;
- calling `memory_search`, running BioCortex, or changing retrieval order;
- moving store or runtime custody;
- changing schemas, MCP exposure, privacy redaction, readiness, or transition;
- deploying or reconnecting clients.
