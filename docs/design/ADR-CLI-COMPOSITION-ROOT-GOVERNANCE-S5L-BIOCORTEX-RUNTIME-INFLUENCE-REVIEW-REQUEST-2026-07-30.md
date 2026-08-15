# ADR: CLI Composition Root Governance S5-L — BioCortex Runtime-Influence Review Request

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

`run_biocortex_retrieval_opt_in_runtime_influence_review_request` currently
combines:

1. composition-root custody of two required and three optional JSON evidence
   inputs, including ordered reads, exact errors, deserialization, and option
   assembly; and
2. a pure review-request planner call followed by deterministic JSON or text
   rendering.

The planner prepares a request for a separate human runtime-influence review.
It does not consume a human decision, approve a runtime adapter, allow default
retrieval influence, connect ordering behavior, or change retrieval order.

## Decision

Move only the pure planner-and-renderer responsibility into private
`cli::biocortex`.

The module receives a fully populated
`BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions` and `as_json`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch;
- ordered required input reads: post-implementation review gate, then redacted
  order artifact;
- ordered optional input reads: redacted evidence aggregate, evidence summary,
  then capability-ledger report packet;
- every exact read and parse error;
- deserialization and complete option assembly;
- every downstream human-decision, store, readiness, transition, deployment,
  and reconnect path.

The planner in `biocortex_shadow.rs` remains unchanged.

## Alternatives

### Keep the mixed adapter in `main.rs`

Lowest immediate diff, but deterministic rendering remains coupled to
authority-sensitive evidence-file custody.

### Move all required and optional file reads

Removes more lines, but hides input precedence and exact error ownership inside
a renderer module.

### Extract the decision packet or store trial in the same unit

Broadens the authority surface and prevents one-boundary-at-a-time
verification.

## Trade-offs

- Repetitive required and optional input handling remains in `main.rs`.
- The private module receives a review-sensitive options type.
- The line reduction is intentionally limited.

These costs preserve explicit custody, error ordering, and reversibility.

## Verification Contract

- Add ownership and custody assertions first and observe the exact RED failure.
- Pass focused review-request boundary, schema, and privacy tests.
- Pass `cli::biocortex` renderer tests.
- Pass fresh locked/offline `cargo check -p ab-bridge --all-targets`.
- Build a fresh candidate binary.
- Compare baseline and candidate help, ready/blocked text and JSON, required
  and optional missing/malformed inputs, error order, exit codes, and privacy
  sentinels.
- Re-check current-main ancestry and both remotes before landing.

## Non-goals

- consuming or writing a human runtime-influence decision;
- approving runtime/default influence or connecting ordering;
- calling `memory_search`, running BioCortex, or changing retrieval order;
- moving file/store custody;
- modifying readiness, transition, deployment, or reconnect behavior;
- deploying or reconnecting clients.
