# ADR: S5-P BioCortex downstream AIO handoff CLI boundary

Date: 2026-07-30

Status: accepted

## Context

The `RetrievalDownstreamAioRuntimeEvidenceHandoff` CLI path combined two
different responsibilities in `main.rs`:

- composition-root custody of required and optional filesystem inputs; and
- invocation and rendering of the pure downstream-AIO handoff planner.

The mixed function made the CLI composition root own planner presentation while
also obscuring which input and authority decisions must remain at the outer
boundary.

## Decision

`main.rs` retains all command schema, dispatch, and input custody:

1. read and parse the required checkpoint-selection JSON;
2. read and parse the required post-semantic-diverse review JSON;
3. only when supplied, read and parse controlled-trial-readiness JSON;
4. preserve that exact error precedence;
5. assemble the complete
   `BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions`.

`cli::biocortex` receives populated options and owns only the pure planner call
and its existing text/JSON rendering.

The extraction is guarded by the CLI ownership test, including exact input
errors, required-before-optional precedence, complete option assembly, and the
absence of filesystem reads from the private CLI module.

## Authority boundary

This refactor does not:

- call AiOT runtime;
- execute LSWR actions;
- call `memory_search`;
- run BioCortex retrieval;
- alter retrieval order;
- enable controlled trials, runtime influence, deployment, or reconnect.

The optional controlled-trial-readiness document remains evidence supplied to
the pure packet planner. It does not grant runtime authority.

## Consequences

The composition root remains the sole custodian of external input and
operator-facing error order. The private CLI module becomes a narrow,
testable presentation adapter. Behavior and CLI output are required to remain
equivalent to the pre-extraction baseline.
