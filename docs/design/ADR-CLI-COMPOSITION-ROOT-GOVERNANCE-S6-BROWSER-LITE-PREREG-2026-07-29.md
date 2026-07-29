# ADR: Preregister BrowserLite CLI family extraction

- Status: Accepted
- Date: 2026-07-29
- Decision scope: `crates/bridge/src/main.rs`
- Coordination: Agent-Bridge forum thread #260
- Base revision: `49141c1ad0d8a6f295436659e7aa25efb322a555`
- Implementation status: preregistered only

## Context

BioCortex S5-C is being audited in a parallel read-only lane. BrowserLite is
an orthogonal composition-root candidate that was previously measured but
deferred only because the S5 name was already authoritative for BioCortex.

BrowserLite has one nested operation and one backend:

- `browser-lite probe obscura`;
- an optional binary override;
- a default-on MCP `tools/list` probe inverted by `--no-mcp-tools`;
- a per-process timeout;
- JSON or text output.

The probe may execute short-lived external commands. It does not construct the
Hub or store, start a persistent backend, mutate browser routing, write memory,
change tool profiles, or grant runtime authority.

## Decision

Preregister S6 to create binary-private `cli::browser_lite` and move:

1. `BrowserLiteOp`;
2. `BrowserLiteBackend`;
3. the complete early BrowserLite dispatch.

The new module may alias the existing public implementation module
`ab_bridge::browser_lite`; it must not modify or duplicate that library logic.

Keep in `main.rs`:

- the root `Cmd::BrowserLite` variant;
- the call to the private BrowserLite dispatcher;
- the post-Hub `Cmd::BrowserLite { .. }` exhaustiveness arm;
- shared root parsing, Hub/store construction, and all unrelated families.

## Preserved Contracts

The implementation must preserve:

- root `browser-lite`, nested `probe`, and backend `obscura` spellings;
- every help paragraph, flag name, optionality rule, and parse failure;
- default backend `obscura`, timeout `5000`, and MCP probing enabled unless
  `--no-mcp-tools` is present;
- binary resolution, subprocess timeout, report fields, JSON/text rendering,
  stdout/stderr, and exit status;
- execution before Hub/store construction and no persistent service;
- default Chrome-backed routing, MCP profiles/manifests, Cargo features,
  runtime policy, and authority.

## Baseline and TDD Gate

Before production movement, capture from the accepted base:

1. root help;
2. `browser-lite --help`;
3. `browser-lite probe --help`;
4. JSON and text output with an explicitly missing binary and fixed timeout,
   both with default MCP probing and `--no-mcp-tools`.

Normalize only fields proven nondeterministic on the accepted base. All other
help, stdout, stderr, and exit artifacts must compare byte-for-byte.

The first Rust edit must add a focused ownership test that fails while schema
and dispatch remain in `main.rs`. Production movement begins only after RED.

Acceptance requires:

- ownership RED then GREEN;
- source-boundary assertions that the root `Cmd` variant and post-Hub
  exhaustiveness arm remain in `main.rs`;
- existing `browser_lite` library tests;
- exact baseline equivalence;
- scoped formatting, `git diff --check`, build, and
  `cargo check --locked --offline -p ab-bridge --all-targets --quiet`.

## Stop Conditions

Stop if the move requires:

- Hub, store, memory, routing, MCP registry, or persistent-service ownership;
- public library changes or duplicated probe logic;
- moving the root `Cmd` enum or unrelated dispatch;
- Cargo/profile/manifest/runtime-policy/authority changes;
- behavior or output drift;
- a newly active overlapping owner.

## Non-Goals

S6 does not authorize BrowserLite routing, persistent backend management,
MCP-tool changes, browser implementation changes, BioCortex audit decisions,
avatar/dream work, deployment, or reconnect.

## Rollback

Revert only the later S6 implementation commit. Keep this ADR as the audit
record; do not preserve a failed move by duplicating schema or probe logic.
