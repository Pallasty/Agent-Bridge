# ADR: CLI Composition Root Governance S5-I — BioCortex Redacted-Order Artifact

## Status

Accepted for implementation on 2026-07-30.

## Context

After S5-H, `main.rs` still owns
`run_biocortex_retrieval_opt_in_redacted_order_artifact`. The adapter combines
composition-root input custody with a pure renderer that computes top-k overlap
and rank movement from validated redacted hash rows.

The underlying planner:

- accepts only runtime-trial or runtime-trial-review packet summaries;
- sanitizes rank rows to hash identifiers and numeric ranks;
- rejects raw query, key, order-key, content, and side-signal material;
- emits no approval and performs no runtime or store action.

Current main also includes a non-overlapping voice-scene commit after S5-H.
That local commit is the current integration base even though the two remotes
had not yet advanced when this decision was recorded.

## Decision

Move only the populated-options planner/renderer into the existing private
`cli::biocortex` module.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema;
- the `RetrievalOptInRedactedOrderArtifact` dispatch arm;
- caller-selected `source_json` file reading;
- exact read and parse error messages;
- JSON deserialization;
- complete `BioCortexRetrievalOptInRedactedOrderArtifactOptions` assembly.

The private module receives a populated options value plus `as_json` and has no
filesystem access.

## Alternatives Considered

### Keep the adapter in `main.rs`

This has zero immediate change risk but leaves another long pure renderer in
the composition root.

### Move input loading into the private module

This removes more lines but violates the established input-custody and exact
error-contract boundary.

### Extract the authorization adapter at the same time

The authorization adapter consumes two inputs and represents a separate
governance boundary. Combining it would enlarge both privacy and authority
proof surfaces.

## Consequences

Positive:

- another pure renderer leaves the composition root;
- raw-data and authority non-claims remain protected by existing tests;
- input custody remains explicit;
- the unit is independently reversible.

Negative:

- deliberate read/parse boilerplate stays in `main.rs`;
- the composition root remains large;
- authorization and later adapters require separate review.

## Verification Contract

1. Add the ownership/input-custody test first.
2. Observe the expected ownership failure in a fresh target.
3. Apply only the minimal renderer movement.
4. Run focused redacted-artifact privacy/packet and module tests.
5. Run locked, offline `ab-bridge --all-targets` checking and CLI building in
   a fresh target.
6. Compare exact current-main base and candidate CLI artifacts for help, valid
   and invalid JSON/text, missing-file, and malformed-JSON cases; normalize
   only `generated_at`.
7. Recheck current-main and both remotes before landing.

## Explicit Non-Goals

S5-I does not:

- execute or move the runtime-trial adapter;
- alter order-diff behavior;
- move authorization, review, store, readiness, or transition gates;
- accept or expose raw query, key, order-key, content, or side-signal payloads;
- call BioCortex or `memory_search`;
- mutate store state, retrieval order, or approval state;
- add a public module or API;
- deploy or reconnect Agent-Bridge.

## Revisit Trigger

Revisit this boundary only if redacted rank-row privacy rules change, or if a
separately authorized stage introduces ordering or approval authority.
