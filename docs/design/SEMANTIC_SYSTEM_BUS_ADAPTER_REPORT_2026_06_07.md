# Semantic System Bus Adapter Report

**Status:** SSB-11 source-backed report surface
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Prior conformance memo:** [Cross-Platform Adapter Conformance](SEMANTIC_SYSTEM_BUS_CROSS_PLATFORM_CONFORMANCE_2026_06_07.md)

## 0. Purpose

SSB-11 adds a compact read-only report that classifies the current Semantic
System Bus adapter family by evidence level:

```text
runtime_backed  -> script/tool/doc assets exist and can be called separately
fixture_backed  -> fixture contracts or static examples exist, but no live check is run
design_only     -> planned adapter shape, no runtime implementation yet
```

The report is intentionally not a probe. It inspects local repo scripts, docs,
and fixtures, then returns a bounded MCP payload.

## 1. MCP Surface

Tool:

```text
semantic_bus_adapter_report
```

Schema:

```text
agent_bridge.semantic_bus.adapter_report.v0
```

Inputs:

- `cwd`: optional Agent-Bridge repo root.
- `include_details`: include per-row asset checks and fixture contract status.
- `include_design_only`: keep planned/no-runtime rows visible.

The tool is exposed to `codex-essential` because it is compact and read-only.
It does not execute desktop probes, call daemon-http, touch Palace, capture
screenshots, restart services, or mutate host state.

## 2. Initial Rows

Runtime-backed rows:

- `linux_desktop_snapshot`
- `linux_desktop_verify`
- `linux_vision_grounding_ocr`
- `macos_ax_probe`
- `macos_ax_verify`
- `local_runtime_health`

Fixture-backed rows:

- `windows_uia_snapshot_fixture`
- `windows_uia_verify_fixture`
- `daemon_http_service_fixture`
- `palace_memory_region_fixture`

Design-only row:

- `windows_uia_runtime_adapter`

## 3. Gap Semantics

The report flags gaps instead of silently promoting weak evidence:

- `fixture_missing_adapter_contract`: fixture exists but lacks
  `adapter_contract` metadata.
- `design_only_no_runtime_or_fixture_contract`: row describes a planned
  adapter only.
- `runtime_assets_or_docs_missing`: a runtime-backed row is missing expected
  script or documentation assets.

This is why `palace_memory_region_fixture` remains fixture-backed but not a
complete adapter contract: the current static fixture is useful for design, but
it should not be treated as a live Palace adapter until it gains explicit
contract metadata or a live read-only report surface.

## 4. Next Slice

SSB-12 landed the runtime health adapter for local service state:

```text
daemon-http health + Palace memory region state -> read-only SSB report
```

This closes the current gap between fixture-described product surfaces and live,
user-visible runtime state without adding mutation. SSB-13 then added the
runtime conformance harness. The next stronger gap is a real Windows UIA runtime
adapter or remote harness coverage from a Windows host.
