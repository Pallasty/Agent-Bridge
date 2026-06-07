# Live Semantic World Runtime Read-Only Bridge MCP Gates

Date: 2026-06-07

Status: P25c draft, MCP registration gate and acceptance matrix

## Purpose

P24/P25a/P25b made the Live Semantic World Runtime ledger readable from
Agent-Bridge without registering a new MCP tool:

- P24 added `build_readonly_bridge_snapshot(...)` over `WorldLedgerSnapshot`.
- P25a added a stable read-only projection fixture.
- P25b added raw snapshot file import and projection examples.

This document defines the gates that must pass before that read-only projection
can be exposed as an MCP tool. It is intentionally docs-only because thread #107
currently owns the `crates/bridge/src/mcp_tools.rs` registry surface for
Semantic System Bus work.

## Current Verdict

Current state after P25b:

- contract status: `CONTRACT_READY`
- registration status: `BLOCKED_BY_ACTIVE_REGISTRY_OWNER`
- active registry owner: #107 SSB-9, which claimed `crates/bridge/src/mcp_tools.rs`
- allowed next action from this lane: acceptance planning and gate review only

The bridge projection is ready to wrap, but this lane should not edit the MCP
registry until the active owner closes or explicitly reassigns that surface.

## Candidate MCP Surface

This is the eventual shape to evaluate, not an implemented tool.

- candidate tool name: `lswr_readonly_bridge_snapshot`
- input: `WorldLedgerSnapshot` JSON object
- optional input: `include_snapshot`, default `false`
- optional input: `source_label`, human-readable provenance label
- output: `agent_bridge.lswr.readonly_bridge_snapshot.v0`
- profile exposure: Standard/All first, not Essential by default
- authority: read-only

If a path-based input is added later, it needs a separate local file-read policy
gate. The safer first MCP shape is object input, leaving file IO as an example
and test fixture path rather than a general host filesystem read surface.

## Non-Goals

This gate package does not:

- register an MCP tool
- edit `crates/bridge/src/mcp_tools.rs`
- add patch, action, invoke, or runtime mutation affordances
- launch Godot, Onsen, or any live semantic runtime
- claim Step D, #92 present wiring, #94 verified-outcome ingestion, or SSB work
- convert human feedback into verification truth

## Gate Matrix

| Gate | Required Evidence | Acceptance Rule |
| --- | --- | --- |
| Snapshot contract | `WorldLedgerSnapshot` imports through `WorldLedger::from_snapshot(...)` | Invalid snapshots fail instead of being normalized. |
| Projection schema | Output schema is `agent_bridge.lswr.readonly_bridge_snapshot.v0` | Schema name is stable and fixture-backed. |
| Read-only affordance | Projection reports `read_only=true`, `mutation_surface=none`, `patch=false`, `action=false`, `invoke=false` | MCP wrapping must not add any mutating capability. |
| Query surface readback | Projection lists action, event, evidence, feedback, and rollback query surfaces | Query surfaces remain inspection/readback contracts only. |
| Raw snapshot handling | `include_snapshot=false` omits raw snapshot by default | Raw inclusion is explicit and test-covered. |
| Fixture replay | Raw snapshot fixture projects to the checked-in projection fixture | Static replay matches generated JSON. |
| No truth laundering | Feedback/acceptance records remain feedback; they do not change verification verdicts | Human response cannot silently become adapter evidence. |
| Registry ownership | No active owner is working in `crates/bridge/src/mcp_tools.rs`, or owner explicitly reassigns | This lane may not collide with #107 SSB-9. |
| Profile gating | Standard/All exposure is tested; Essential remains hidden unless separately approved | New tool does not expand compact/essential tool surface by default. |
| Telemetry readiness | Tool dispatch can be audited after registration | Registration should include enough tool metadata to inspect usage. |

## Required Regression Set Before Registration

Before any MCP registration commit is accepted, rerun the bridge checks that
prove the wrapper is still transport-only:

```sh
cargo test -p ab-bridge lswr_snapshot_bridge -- --nocapture
cargo test -p ab-bridge --test lswr_readonly_bridge_fixture -- --nocapture
cargo test -p ab-bridge --test lswr_readonly_bridge_file_io -- --nocapture
cargo run -p ab-bridge --example lswr_readonly_bridge_project_snapshot -- crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json
cargo run -p ab-bridge --example lswr_readonly_bridge_project_snapshot -- crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json --include-snapshot
cargo check -p ab-bridge --all-targets
rustfmt --check crates/bridge/src/lswr_snapshot_bridge.rs crates/bridge/examples/lswr_readonly_bridge_projection.rs crates/bridge/examples/lswr_readonly_bridge_project_snapshot.rs crates/bridge/tests/lswr_readonly_bridge_fixture.rs crates/bridge/tests/lswr_readonly_bridge_file_io.rs
git diff --check
```

Registration-specific checks should then add:

```sh
AGENT_BRIDGE_TOOL_PROFILE=standard cargo test -p ab-bridge world_tools --lib -- --nocapture
AGENT_BRIDGE_TOOL_PROFILE=all cargo test -p ab-bridge world_tools --lib -- --nocapture
```

The exact test name can change with the eventual MCP registry implementation,
but the acceptance point is stable: standard/all must expose the read-only tool
only when intended, and essential must not inherit it accidentally.

## Acceptance States

`READY_FOR_REGISTRATION`

All gates pass, #107 or any other registry owner has released
`crates/bridge/src/mcp_tools.rs`, and the MCP wrapper plan remains read-only.

`BLOCKED_BY_ACTIVE_REGISTRY_OWNER`

The core contract and examples are ready, but another lane owns the registry
surface. This is the current state.

`NOT_READY`

Any fixture replay, import validation, raw snapshot default, or regression check
fails.

`OUT_OF_SCOPE`

The requested work adds mutation, action execution, live runtime invocation, or
verified-outcome ingestion. Those belong to later Step D/#92/#94 lanes, not this
read-only bridge registration gate.

## First Registration Plan

When the registry surface is clear, the first implementation should be a narrow
transport wrapper around the existing bridge module:

1. Accept a `WorldLedgerSnapshot` JSON object and `include_snapshot=false`.
2. Deserialize with `ab-world-core`.
3. Call `build_readonly_bridge_snapshot(...)`.
4. Return the projection unchanged.
5. Add profile-gating tests before posting DONE.

Do not add file-path input, runtime launch, or any patch/action affordance in the
first registration commit. Those require separate authority decisions and a new
acceptance post.
