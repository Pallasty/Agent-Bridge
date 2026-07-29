# ADR: Preregister BioCortex approval-preview CLI extraction

- Status: Accepted
- Date: 2026-07-29
- Decision scope: `crates/bridge/src/main.rs`
- Coordination: Agent-Bridge forum thread #258
- Base revision: `001fd07de3a7793de90dd76e8c512938bcc0a1cd`
- Implementation status: preregistered only

## Context

S5-A established binary-private `cli::biocortex` ownership for the two
lowest-authority BioCortex evidence-entry adapters and their text formatter.
The remaining 26 executors still cross several distinct effect boundaries.

The nearest remaining executor,
`run_biocortex_retrieval_approval_packet`, delegates to
`biocortex_retrieval_runtime_approval_packet_preview` and renders the returned
packet. The command documentation and payload boundary explicitly state that
it is review preparation only. It does not run BioCortex, open `state.db`,
write a fixture, mutate memory or retrieval order, write approval state, or
grant runtime authority.

The adjacent `run_biocortex_replay_compare` is not equivalent: it may open
`state.db`, collect live evidence, write a caller-selected fixture, and execute
the external BioCortex adapter. Later opt-in commands form an ordered
authorization and runtime-transition evidence ladder and require a cumulative
boundary audit before physical movement.

## Decision

Preregister one S5-B implementation that moves only
`run_biocortex_retrieval_approval_packet` from `main.rs` into the existing
binary-private `cli::biocortex` module.

Keep in `main.rs`:

- the complete 28-variant `BioCortexOp` clap schema;
- the `RetrievalApprovalPacket` dispatch arm;
- construction of `BioCortexRetrievalApprovalPacketOptions` from clap values;
- `run_biocortex_replay_compare`;
- all retrieval opt-in status, planning, review, execution, trial, order,
  store, diagnostics, readiness, transition, evidence, handoff, fixture, and
  shadow executors;
- all store construction, feature gates, policy, and authority decisions.

No public library API or new generic formatter is created. The moved executor
continues to use the S5-A `shadow_json_display` helper in the same private
module.

## Preserved Contracts

The implementation must preserve:

- root `bio-cortex` and nested `retrieval-approval-packet` spellings;
- every flag, help paragraph, optionality rule, and parse failure;
- option assembly and dispatch before shared Hub construction;
- JSON schema, fields, null/default behavior, and serialization;
- text heading, field order, missing-evidence truncation, stdout/stderr, and
  exit status;
- all fail-closed defaults, including no runtime approval, no approval writes,
  no search-order change, and separate human-approval requirements;
- existing tool profiles, MCP manifests, store schemas, retrieval behavior,
  feature gates, runtime policy, and authority.

Physical movement must not reinterpret an agent attestation, human
authorization field, gate field, or readiness field as approval.

## Baseline and TDD Gate

Before production movement, capture from exact base `001fd07d`:

1. `agent-bridge --help`;
2. `agent-bridge bio-cortex --help`;
3. `agent-bridge bio-cortex retrieval-approval-packet --help`;
4. default JSON and text output;
5. JSON and text output with every command option populated using fixed
   deterministic values.

All help, stdout, stderr, and exit-status artifacts must compare byte-for-byte.
No normalization is expected because this preview packet has no generated
timestamp.

The first Rust edit must add a focused ownership test that fails while
`run_biocortex_retrieval_approval_packet` remains defined in `main.rs`.
Production movement is allowed only after that RED is observed.

Acceptance requires:

- ownership RED then GREEN;
- a source-boundary assertion that ReplayCompare, `SqliteStore`, store trials,
  runtime-transition gates, `BioCortexOp`, and option assembly remain outside
  `cli::biocortex`;
- existing approval-preview and BioCortex capability-ledger tests;
- byte-equivalent baseline artifacts;
- scoped `rustfmt`, `git diff --check`, and
  `cargo check --locked --offline -p ab-bridge --all-targets --quiet`.

## Stop Conditions

Stop and return to design if:

- the selected executor needs `SqliteStore`, StateStore, Hub, MCP, filesystem
  writes, memory mutation, retrieval mutation, or runtime-transition policy;
- clap schema, dispatch ownership, or option assembly must move;
- a public API, Cargo feature, tool profile, or manifest must change;
- output, exit, error, policy, or authority semantics drift;
- another active owner begins overlapping `main.rs` work.

## Explicit Non-Goals

S5-B does not authorize:

- ReplayCompare extraction;
- any retrieval opt-in, store, diagnostics, evidence, readiness, transition,
  authorization-decision, handoff, fixture, or shadow extraction;
- BioCortex execution, runtime linking, retrieval influence, approval writes,
  memory writes, policy changes, deployment, or reconnect;
- changes to avatar, dream, Instinct, `mcp_tools.rs`, library APIs, or Cargo.

## Rollback

Revert only the later S5-B implementation commit, restoring the executor
definition and imports to `main.rs`. Keep this ADR as the audit record. Do not
preserve a failed extraction by moving dispatch, duplicating the formatter, or
widening module visibility.
