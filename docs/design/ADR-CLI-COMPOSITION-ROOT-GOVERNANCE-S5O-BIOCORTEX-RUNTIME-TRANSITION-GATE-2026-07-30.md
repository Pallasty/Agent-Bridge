# ADR: CLI Composition Root Governance S5-O — BioCortex Runtime Transition Gate

## Status

Accepted for one behavior-preserving, no-deploy extraction unit.

## Context

The runtime-transition command has three distinct responsibilities:

1. `main.rs` reads and parses one runtime-readiness packet;
2. `main.rs` combines the explicit CLI disable flag with the current
   `AGENT_BRIDGE_BIOCORTEX_RETRIEVAL_DISABLE` environment state;
3. a pure synchronous planner evaluates the populated options and renders a
   read-only transition-gate packet.

The environment check is runtime authority custody. Moving it into a
renderer-oriented module would blur the fail-closed operator boundary.

The populated-options planner and renderer are deterministic apart from the
existing packet timestamp and have no file, environment, store, retrieval, or
deployment side effects.

## Decision

Move only the populated-options planner-and-renderer adapter into private
`cli::biocortex`.

`main.rs` retains:

- the complete `BioCortexOp` Clap schema and dispatch;
- the runtime-readiness packet path, read, parsing, and exact errors;
- complete `BioCortexRetrievalOptInRuntimeTransitionGateOptions` assembly;
- the exact `--operator-disabled ||
  cli_env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV)` decision;
- `cli_env_truthy`, the disable-environment constant, and all runtime,
  retrieval, store, deployment, and reconnect paths.

The planner in `biocortex_shadow.rs` remains unchanged.

## Alternatives

### Keep the mixed adapter in `main.rs`

Avoids a diff, but leaves deterministic packet rendering coupled to input and
environment custody.

### Move environment evaluation with the renderer

Reduces more composition-root code, but transfers operator-disable authority
into a module that otherwise consumes already-authorized values.

### Combine the following runtime executors

Would create a larger line-count reduction, but would mix this read-only gate
with store access, side-signal execution, or downstream authority.

## Trade-offs

- File and environment handling remain visibly repetitive in `main.rs`.
- The private module can report `transition_allowed` for already-populated
  options.
- The line reduction is intentionally smaller than moving the whole command.

These costs keep operator state fail-closed and preserve a narrow,
independently reversible unit.

## Verification Contract

- Observe the exact ownership RED before production changes.
- Pass ownership, readiness-input, and operator-disable custody assertions.
- Pass focused runtime-transition planner, MCP schema, and privacy tests.
- Pass repository pre-commit and a fresh locked/offline all-target check.
- Compare independently rebuilt baseline and candidate binaries for help,
  allowed and blocked transitions, text and JSON, CLI and environment disable
  paths, missing and malformed readiness input, exit codes, stdout/stderr, and
  privacy sentinels.
- Reconcile concurrent `master` changes before dual-remote landing.

## Non-goals

- reading environment variables from `cli::biocortex`;
- changing truthy-value parsing or CLI/environment precedence;
- granting or executing a retrieval transition;
- calling `memory_search`, running BioCortex, or accessing `state.db`;
- changing retrieval order, schemas, MCP exposure, or privacy redaction;
- deployment or client reconnect.
