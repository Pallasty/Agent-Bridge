# Live Semantic World Runtime Read-Only Bridge Exposure Dry-Run

Status: P32 draft, descriptor-driven exposure planning.

## Purpose

P32 evaluates a future wrapper exposure request without changing the MCP registry.

P31 made the wrapper boundary explicit. P32 turns that boundary into a dry-run evaluator so a candidate tool exposure can be checked as data before any real `mcp_tools.rs` change exists.

## Schema

The dry-run schema is `agent_bridge.lswr.readonly_bridge_wrapper_exposure_dry_run.v0`.

Top-level fields:

- `schema`
- `descriptor_schema`
- `wrapper_name`
- `requested_tool_name`
- `requested_profile`
- `verdict`
- `applies_registry_change`
- `checks`
- `guidance`

## Dry-Run Request

The safe default request is generated from the P31 descriptor:

- tool name `lswr_readonly_bridge_display`
- requested profile `all`
- registry mode `dry_run_only`
- explicit report packet payload input
- P28 report packet input schema
- P30 display model output schema
- wrapper-ready acceptance guard required
- no host path, live runtime, GUI capture, patch, action, invoke, or mutation affordance

The dry-run never applies a registry change. Even when the verdict is `accepted`, `applies_registry_change` remains false.

## Checks

P32 emits required checks:

- `descriptor_state`
- `registry_mode`
- `tool_name`
- `profile_gate`
- `schema_contract`
- `input_safety`
- `mutation_safety`
- `acceptance_guard`

Any failed required check rejects the dry-run request.

## Rejection Cases

Tests cover rejection for:

- Codex essential profile exposure
- host path, live runtime, or GUI capture input
- action/invoke mutation affordances
- output schema mismatch
- missing wrapper-ready acceptance guard

## Usage

The example prints the default dry-run:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_exposure_dry_run
```

P32 intentionally does not touch `mcp_tools.rs`. A later exposure slice can use this dry-run as a preflight before adding a real profile-gated MCP registry entry.
