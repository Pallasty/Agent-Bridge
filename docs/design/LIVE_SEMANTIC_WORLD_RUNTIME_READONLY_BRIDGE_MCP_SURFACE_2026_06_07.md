# Live Semantic World Runtime Read-Only Bridge MCP Surface

Status: P35 draft, post-registry surface readback report.

## Purpose

P35 adds stable readback evidence for the P34 MCP registry change.

P34 registered the `lswr_readonly_bridge_display` wrapper as a real MCP tool under `Tier::Niche`. P35 does not add another MCP tool. It builds a report directly from the actual `mcp_tools.rs` registry and tool schema so reviewers can compare expected exposure against the current code without relying only on ad hoc unit-test assertions.

## Schema

The report schema is `agent_bridge.lswr.readonly_bridge_display_mcp_surface_report.v0`.

Top-level fields:

- `schema`
- `tool`
- `verdict`
- `visible_in`
- `profile_rows`
- `tool_schema`
- `checks`
- `safety_boundary`
- `guidance`
- `report_markdown`

## Expected Surface

The wrapper is expected to be visible in:

- `profile-all`
- `all-dev`

The wrapper is expected to be hidden from:

- `profile-standard`
- `codex-essential`
- `codex-lean`
- `claude-standard`
- `gemini-lean`
- `hook-lifecycle`

This matches the P34 policy: available only when the caller intentionally opens the full all-profile or all-dev surface.

## Input Contract

The tool schema must expose only:

- `report_packet`

It must not expose:

- host path inputs
- packet path inputs
- live runtime handles
- GUI capture inputs
- screenshot or image inputs
- patch/action/invoke fields
- unknown additional properties

The report checks the frozen schema facts from `FinalizedToolRegistry::list()`, not a manually copied schema description.

## Safety Boundary

P35 itself does not:

- add another MCP tool
- deploy or reconnect MCP
- launch a live LSWR host
- capture GUI state
- read host paths
- patch world state
- write artifacts
- open #94 ingestion

It only gives a deterministic code-level report over the registry state that P34 introduced.

## Usage

Print the report:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_mcp_surface
```

Focused verification:

```sh
cargo test -p ab-bridge --test lswr_readonly_bridge_mcp_surface -- --nocapture
```

Follow-up deployment verification, when requested, should compare the live MCP client tool list after redeploy/reconnect against this report. This slice intentionally does not perform that deployment.
