# ADR: CLI Composition Root Governance S5-H — BioCortex Order-Diff Packet

## Status

Accepted for implementation on 2026-07-30.

## Context

After S5-G, `main.rs` still owns the complete
`run_biocortex_retrieval_opt_in_order_diff_packet` adapter. The adapter mixes
composition-root responsibilities with a pure, read-only packet renderer:

- reading and parsing a caller-selected JSON file;
- assembling `BioCortexRetrievalOptInOrderDiffPacketOptions`;
- calling the pure order-diff planner;
- rendering the resulting packet as JSON or stable text.

The planner consumes only a runtime-trial or runtime-trial-review packet and
emits hash-only comparison evidence. Its output explicitly denies approval,
BioCortex execution, `memory_search`, store mutation, and retrieval-order
changes.

## Decision

S5-H moves only the populated-options planner/renderer into the existing
private `cli::biocortex` module.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema;
- the `RetrievalOptInOrderDiffPacket` dispatch arm;
- `source_json` file reading;
- the exact read and parse error messages;
- JSON deserialization;
- complete option assembly.

The private module receives a populated
`BioCortexRetrievalOptInOrderDiffPacketOptions` value and the `as_json` flag.
It performs no filesystem access.

## Alternatives Considered

### Keep the mixed adapter in `main.rs`

This avoids a change but leaves pure presentation logic in the composition
root and stalls the incremental governance sequence.

### Move file loading into `cli::biocortex`

This would reduce more lines in `main.rs`, but it would blur the established
input-custody boundary and weaken exact error-contract ownership.

### Extract order-diff and redacted-order adapters together

The functions are adjacent and structurally similar, but a combined extraction
would enlarge the proof surface without being necessary. Redacted-order
custody remains a separate future decision.

## Consequences

Positive:

- one more pure renderer leaves the composition root;
- input and error custody remain explicit;
- the private module gains no filesystem, store, or runtime authority;
- the change remains independently reversible.

Negative:

- the dispatch arm still contains deliberate read/parse boilerplate;
- `main.rs` remains large;
- another narrow stage is required for any later renderer.

## Verification Contract

Implementation requires:

1. a test-first ownership assertion that fails because the renderer is still
   in `main.rs`;
2. the expected RED failure from a fresh target;
3. minimal production movement;
4. focused order-diff and module tests;
5. locked, offline `ab-bridge --all-targets` checking and CLI building from a
   fresh target;
6. base-versus-candidate CLI comparison for help, valid and invalid JSON/text,
   missing-file, and malformed-JSON paths;
7. current-main and dual-remote convergence checks before closure.

## Explicit Non-Goals

S5-H does not:

- execute or move the runtime-trial adapter;
- move the redacted-order artifact adapter;
- touch authorization, post-implementation review, store, readiness, or
  transition gates;
- call BioCortex or `memory_search`;
- mutate memory/store state or retrieval order;
- write approval;
- add a public module or API;
- deploy or reconnect Agent-Bridge.

## Revisit Trigger

Revisit the boundary only if a later renderer cannot preserve composition-root
input custody, or if an explicitly authorized stage changes the runtime or
ordering authority model.
