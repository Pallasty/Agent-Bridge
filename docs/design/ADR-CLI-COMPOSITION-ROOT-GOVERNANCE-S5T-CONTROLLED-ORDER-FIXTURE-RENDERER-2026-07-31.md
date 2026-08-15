# ADR: CLI composition-root governance S5-T controlled-order fixture renderer

## Status

Accepted on 2026-07-31.

## Context

`main.rs` still rendered the completed controlled-order fixture payload after performing the explicit write acknowledgement, input loading, non-production Store writes, diagnostics, threshold decisions, and payload construction. The presentation-only tail is a narrow boundary already established for neighboring BioCortex evidence commands.

## Decision

Move only JSON/text rendering of the completed payload to private `cli::biocortex` as `run_biocortex_retrieval_opt_in_controlled_order_fixture_result`.

Keep in `main.rs`:

- clap schema and dispatch;
- `--allow-non-production-store-writes` enforcement;
- database selection, file loading, fixture validation, and exact errors;
- query and option assembly;
- `SqliteStore` opening and fixture-memory writes;
- diagnostic execution, expected-threshold decisions, schema custody, and payload construction.

## Trade-offs

The renderer reads diagnostic counts through payload pointers rather than local variables. This adds small pointer verbosity, but gives the presentation boundary one input and keeps all authority-bearing state in the composition root.

## Consequences

The command remains behavior-compatible while `main.rs` loses a presentation-only block. No Store, retrieval, approval, MCP, deployment, or runtime authority moves into the CLI module.

## Revisit trigger

Revisit only if a typed presentation model replaces the existing JSON payload contract; do not move Store or diagnostic execution merely to reduce line count.
