# ADR: CLI Composition Root Governance S5-K — BioCortex Post-Implementation Review Gate

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

`run_biocortex_retrieval_opt_in_post_implementation_review_gate` currently
combines:

1. composition-root custody of an authorization-decision packet and opt-in
   experiment plan, including ordered file reads, exact errors,
   deserialization, and option assembly; and
2. a pure review-gate planner call followed by deterministic JSON or text
   rendering.

The planner may report that evidence is ready for a separate human
runtime-influence review. It explicitly does not complete that review, approve
a runtime adapter, allow default retrieval influence, connect ordering
behavior, or change retrieval order.

## Decision

Move only the pure planner-and-renderer responsibility into private
`cli::biocortex`.

The module receives a fully populated
`BioCortexRetrievalOptInPostImplementationReviewGateOptions` and `as_json`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch;
- the ordered authorization-decision-packet then opt-in-plan file reads;
- exact read and parse errors;
- deserialization and complete option assembly;
- every downstream runtime-review, store, readiness, transition, deployment,
  and reconnect path.

The planner in `biocortex_shadow.rs` remains unchanged.

## Alternatives

### Keep the mixed adapter in `main.rs`

Lowest immediate diff, but deterministic rendering remains coupled to
filesystem custody.

### Move the complete adapter including both file reads

Removes more lines, but broadens the private renderer module into
authority-sensitive input custody and obscures error-order ownership.

### Extract the planner or downstream review workflow

Unnecessary for this unit and materially expands the authority boundary.

## Trade-offs

- Repetitive input handling remains in `main.rs`.
- The private module receives a review-sensitive packet type.
- The line reduction is intentionally limited.

These costs preserve explicit custody and reversibility.

## Verification Contract

- Add the ownership and custody assertions first and observe an exact RED
  failure.
- Pass focused review-gate schema, boundary, and privacy tests.
- Pass `cli::biocortex` renderer tests.
- Pass fresh `cargo check --locked --offline -p ab-bridge --all-targets`.
- Build a fresh candidate binary.
- Compare baseline and candidate help, ready/blocked text and JSON, missing and
  malformed inputs, error order, exit codes, and privacy sentinels.
- Re-check current-main ancestry and both remotes before landing.

## Non-goals

- changing review-gate or authorization policy;
- completing human runtime-influence review;
- approving runtime/default influence or connecting ordering;
- modifying stores, memory, runtime, readiness, transition, or deployment;
- deploying or reconnecting clients.
