# ADR: S5-R BioCortex evidence-summary renderer boundary

Date: 2026-07-31

Status: accepted

## Context

`RetrievalOptInEvidenceSummary` combines three distinct responsibilities: external JSON custody,
evidence interpretation and payload construction, and CLI presentation. The first two contain
schema, safety, readiness, and authority decisions that belong in the composition root. The final
step operates only on the already-populated payload.

## Decision

`main.rs` retains the complete command schema and dispatch, batch diagnostics and controlled
fixture file custody, optional runtime-readiness custody, exact errors and input precedence, all
evidence interpretation, metadata assembly, and payload construction.

The existing private `cli::biocortex` module owns only
`run_biocortex_retrieval_opt_in_evidence_summary(payload, as_json)`: canonical pretty JSON or the
existing compact text projection derived from the populated payload.

Moving the complete evidence planner was rejected because it would move hundreds of lines of
schema and authority policy merely to reduce the composition-root line count. A new module was
also rejected because this remains one `BioCortexOp` presentation adapter and already shares the
private module's JSON-display helper.

## Authority boundary

This refactor does not move filesystem custody, call Store, Hub, memory search, or BioCortex,
change retrieval order, write approval or memory, register an MCP tool, grant runtime/default
influence, deploy Agent-Bridge, or reconnect a client.

## Verification

The ownership contract requires the builder and input order in `main.rs`, requires the renderer in
`cli::biocortex`, and forbids evidence-summary loaders and schema policy in the private module.
Focused tests, independent baseline/candidate CLI comparison, and a fresh all-target gate must
preserve both optional-readiness output shapes and all error behavior.
