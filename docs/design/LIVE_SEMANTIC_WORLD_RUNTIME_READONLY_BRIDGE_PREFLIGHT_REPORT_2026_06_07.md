# Live Semantic World Runtime Read-Only Bridge Preflight Report

Status: P33 draft, wrapper exposure readiness report.

## Purpose

P33 turns the P31 descriptor and P32 exposure dry-run into a report payload for human and agent review.

The report does not register a tool. It packages the current wrapper boundary, safety contract, dry-run checks, guidance, and stable Markdown into a single preflight artifact that can be read before opening any real MCP registry slice.

## Schema

The report schema is `agent_bridge.lswr.readonly_bridge_wrapper_preflight_report.v0`.

Top-level fields:

- `schema`
- `descriptor_schema`
- `dry_run_schema`
- `wrapper_name`
- `verdict`
- `status`
- `registry_boundary`
- `safety_boundary`
- `check_rows`
- `guidance`
- `report_markdown`

## Verdicts

`ready_for_registry_review` means:

- the descriptor and dry-run match;
- the dry-run verdict passed;
- no registry change was applied;
- the wrapper remains read-only and descriptor-driven.

`blocked` means at least one required preflight check failed. A blocked report is not suitable for registry review.

## Checks

P33 adds `preflight_consistency` before carrying forward the P32 dry-run checks. It verifies:

- descriptor schema matches the dry-run descriptor schema;
- wrapper name matches;
- requested tool name matches the descriptor candidate tool;
- `applies_registry_change=false`.

The P32 checks remain visible in the report:

- `descriptor_state`
- `registry_mode`
- `tool_name`
- `profile_gate`
- `schema_contract`
- `input_safety`
- `mutation_safety`
- `acceptance_guard`

## Boundaries

P33 still avoids:

- `mcp_tools.rs` changes
- real MCP tool registration
- live runtime launch
- GUI capture
- host path input
- patch/action/invoke or other mutation affordances
- filesystem writes outside the report fixture/test/doc files

## Usage

The example prints the default report:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_preflight_report
```

The next slice can either preserve this report as the acceptance artifact for a registry patch, or add an MCP registry patch behind an explicit profile gate and keep these preflight checks as tests.
