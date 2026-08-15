# ADR: S5-Q LSWR interaction-feedback preflight CLI boundary

Date: 2026-07-30

Status: accepted

## Context

The `LswrInteractionFeedbackConsumptionPreflight` command is a
`BioCortexOp` variant that reads one explicit JSON input and invokes the pure
LSWR interaction-feedback consumption preflight. Its `main.rs` executor mixed
external input custody with pure packet construction and presentation.

S5-P established the adjacent downstream-AIO boundary: the composition root
retains external input and authority decisions while a private CLI adapter owns
pure planning and rendering.

## Decision

`main.rs` retains:

1. the complete Clap schema and dispatch arm;
2. required `input_json` filesystem custody;
3. the exact read error;
4. the exact parse error and read-before-parse precedence;
5. construction of the populated `serde_json::Value`.

The existing private `cli::biocortex` module receives that populated value and
owns only:

1. `build_interaction_feedback_packet_consumption_preflight(&input)`;
2. the existing canonical JSON output;
3. the existing compact text presentation.

Reusing `cli::biocortex` is the smallest boundary because the command remains a
`BioCortexOp` variant and already uses that module's generic JSON display
helper. A new one-function LSWR CLI module would add indirection without
changing authority or behavior.

## Authority boundary

This refactor does not:

- query live LSWR state;
- mutate world or runtime state;
- register or expose an MCP tool;
- access a store or write memory;
- upgrade a `not_verified` world verdict;
- add default-profile exposure;
- move the command schema;
- deploy or reconnect Agent-Bridge.

The preflight remains explicit-input-only, read-only, and incapable of granting
runtime or verification authority.

## Verification

The ownership contract requires the adapter in `cli::biocortex`, keeps input
reads and exact errors in `main.rs`, and forbids filesystem custody in the
private module. Focused preflight tests and independent baseline/candidate CLI
comparison must additionally preserve accepted and blocked output, malformed
input behavior, and error precedence.
