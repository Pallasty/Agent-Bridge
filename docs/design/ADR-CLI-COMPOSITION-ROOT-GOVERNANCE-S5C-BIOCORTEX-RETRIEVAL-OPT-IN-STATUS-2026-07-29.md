# ADR: Preregister BioCortex retrieval opt-in status extraction

- Status: Accepted
- Date: 2026-07-29
- Decision scope: `crates/bridge/src/main.rs`
- Coordination: Agent-Bridge forum thread #259
- Base revision: `49141c1ad0d8a6f295436659e7aa25efb322a555`
- Implementation status: preregistered only

## Context

S5-A and S5-B established a binary-private `cli::biocortex` boundary for
evidence-entry and approval-preview renderers. The remaining BioCortex
executors are not one effect family: they include external process execution,
input-file consumption, temporary stores, controlled fixtures, diagnostics,
readiness, transition, authorization, and runtime-influence evidence.

The narrowest remaining executor is
`run_biocortex_retrieval_opt_in_status`. It delegates to
`biocortex_retrieval_opt_in_audit_report` and renders the returned JSON value.
The executor itself does not read files, open a database or store, call
`memory_search`, run BioCortex, include raw query/keys/content, mutate
retrieval order, write approval state, or grant authority.

The library report observes the existing compile feature and two environment
gates. It remains fail-closed and returns baseline ordering. Four optional
JSON evidence files are read and parsed before the executor is called; those
operations belong to the root dispatch boundary and are not part of S5-C.

## Decision

Move only `run_biocortex_retrieval_opt_in_status` from `main.rs` into the
existing binary-private `cli::biocortex` module.

The implementation may add only the private imports and re-export required by
that move. It must reuse `shadow_json_display`.

Keep in `main.rs`:

- the complete `BioCortexOp` clap schema and nested help;
- the `BioCortexOp::RetrievalOptInStatus` dispatch arm;
- all four `read_optional_json_file` calls;
- construction of `BioCortexRetrievalOptInAuditOptions`;
- ReplayCompare and every dry-run, review, execution, runtime-trial, order,
  store, diagnostics, readiness, transition, authorization, evidence, shadow,
  fixture, and handoff executor;
- `read_optional_json_file`, CLI environment helpers, store construction,
  Hub, MCP, feature, policy, and authority behavior.

No public API, Cargo surface, generic formatter, or new abstraction is
created.

## Preserved Contracts

S5-C must preserve:

- root `bio-cortex retrieval-opt-in-status` spelling;
- every flag, default, repeatability rule, help paragraph, and parse failure;
- optional JSON file read/parse context, stderr, and exit status;
- option assembly and dispatch before shared Hub construction;
- compile-feature and environment-gate observation;
- query and baseline-key hashing/redaction;
- JSON schema, values, pretty-printing, and top-level `generated_at`;
- text heading, line ordering, fallback/default rendering, and newlines;
- baseline-returned, no ordering connection, no search-order mutation, no raw
  key/content, no runtime approval, and fail-closed gate semantics;
- profiles, manifests, stores, retrieval behavior, runtime policy, and
  authority.

Moving this renderer must not convert audit observability into readiness,
authorization, approval, or runtime influence.

## Baseline and TDD Gate

Before production movement, capture from exact base `49141c1a` under a frozen
environment with both retrieval opt-in environment variables unset:

1. `agent-bridge --help`;
2. `agent-bridge bio-cortex --help`;
3. `agent-bridge bio-cortex retrieval-opt-in-status --help`;
4. default JSON and text output;
5. populated JSON and text output using fixed mode, opt-in, query, repeated
   baseline keys, side-signal status, fallback reason, and latency;
6. missing optional JSON file stderr and exit status;
7. malformed optional JSON file stderr and exit status.

Normalize only JSON fields named `generated_at`: the top-level report epoch
and the nested gate-report epoch. Compare every other stdout byte, all stderr,
and exit status exactly.

The first Rust edit must extend the cumulative ownership test and fail because
`run_biocortex_retrieval_opt_in_status` remains in `main.rs`. Production
movement is allowed only after that RED is observed.

Acceptance requires:

- ownership RED then GREEN;
- cumulative boundary assertions retaining schema, dispatch, option assembly,
  optional-file loading, ReplayCompare, dry-run, store, runtime-transition,
  `SqliteStore`, and `BioCortexOp` in the root;
- focused audit tests for baseline hashing/redaction and non-FTS rejection;
- existing approval-preview and formatter tests;
- exact baseline equivalence;
- scoped `rustfmt`, `git diff --check`, and
  `cargo check --locked --offline -p ab-bridge --all-targets --quiet`.

Use a fresh `CARGO_TARGET_DIR` for each worktree/evidence phase.

## Stop Conditions

Stop and return to design if:

- file reading/parsing or option assembly must move;
- the executor needs `SqliteStore`, StateStore, Hub, MCP, an external process,
  a write, or runtime-transition policy;
- schema, dispatch, public API, Cargo, profile, or manifest changes;
- formatter duplication or generalization;
- output, error, exit, environment-gate, policy, or authority drift;
- overlapping `main.rs` ownership appears.

## Rejected Alternatives

### Move status and dry-run together

Rejected because the dry-run is a separate planning surface with different
options and future-side-signal semantics. Similar rendering does not prove one
effect boundary.

### Move optional JSON loading with the executor

Rejected because it would expand a pure renderer into filesystem parsing and
change error ownership.

### Move the complete opt-in ladder

Rejected because review, execution, trials, stores, diagnostics, readiness,
transition, and authorization carry distinct evidence and authority
contracts.

## Rollback

Revert only the S5-C implementation commit, restoring the executor definition
and imports to `main.rs`. Preserve this ADR as the audit record. Do not add
aliases, duplicate the formatter, widen visibility, or move routing to salvage
a failed extraction.
