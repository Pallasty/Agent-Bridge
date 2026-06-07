# Semantic System Bus Runtime Health

**Status:** SSB-12 live read-only runtime report
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Previous slice:** [Semantic System Bus Adapter Report](SEMANTIC_SYSTEM_BUS_ADAPTER_REPORT_2026_06_07.md)

## 0. Purpose

SSB-12 turns two fixture-described Agent-Bridge product surfaces into one live,
read-only Semantic System Bus report:

```text
daemon-http healthz + Palace healthz + Palace graph state
    -> agent_bridge.semantic_bus.runtime_health.v0
```

The goal is runtime evidence, not control. The tool observes whether local
services are reachable and whether Palace can return a memory graph, then emits
semantic service and memory-region objects that Codex can reason over directly.

## 1. MCP Surface

Tool:

```text
semantic_bus_runtime_health
```

Schema:

```text
agent_bridge.semantic_bus.runtime_health.v0
```

Inputs:

- `daemon_http_url`: defaults to `http://127.0.0.1:7878`.
- `palace_url`: defaults to `http://127.0.0.1:7979`.
- `include_all`: when true, calls `/api/graph?all=1`.
- `check_semantic_events`: probes `/api/semantic-events` when present.
- `include_raw`: includes parsed raw Palace graph/events JSON.
- `timeout_ms`: bounded per-request timeout, clamped to 500..10000 ms.

The tool is exposed to `codex-essential` because it is compact, read-only, and
directly useful after MCP/daemon/Palace restarts.

## 2. Safety Contract

The tool only performs bounded HTTP GET requests:

- `GET {daemon_http_url}/healthz`
- `GET {palace_url}/healthz`
- `GET {palace_url}/api/graph`
- optional `GET {palace_url}/api/semantic-events`

It never:

- starts or restarts daemon-http;
- starts or restarts Palace;
- mutates Palace files;
- writes memory records or graph edges;
- captures screenshots;
- injects desktop input.

Unavailable endpoints are represented inside the payload as `blocked` or
`degraded` state. They should not become MCP tool errors unless the MCP process
itself fails.

## 3. Runtime Semantics

The report emits three semantic object families when data is available:

- `service.http.daemon`: daemon-http service health.
- `service.http.ui`: Palace service health.
- `memory.region`: Palace memory-region graph state.

Palace graph statistics mirror the existing Palace footer/event logic:

- `nodes`
- `edges`
- `sqlite_nodes`
- `markdown_nodes`
- `explicit_edges`
- `coactivation_edges`
- `orphan_nodes`
- `hub_nodes`
- `fresh_nodes`
- `stale_nodes`
- `connected_ratio`
- `explicit_density`

This lets Codex inspect the memory topology from structured state instead of
reading the Palace UI or screenshot.

## 4. Optional Semantic Events Endpoint

`/api/semantic-events` is useful when the running Palace binary includes the
newer SSB endpoint. Older Palace services may only expose `/healthz` and
`/api/graph`.

For that reason, SSB-12 treats `/api/semantic-events` as optional:

- missing or `404` endpoint: keep `status=ready` if healthz and graph are good;
- invalid event JSON: record the optional check as failed;
- valid event JSON: include the parsed event payload when `include_raw=true`.

The required acceptance path is service health plus graph state.

## 5. Acceptance

Source acceptance:

- `semantic_bus_runtime_health` is registered in the MCP tool registry.
- The tool is included in the Codex essential direct extras list.
- Unit tests verify registry exposure and optional endpoint handling.
- `semantic_bus_adapter_report` lists `local_runtime_health` as runtime-backed.

Runtime acceptance:

- local daemon-http `/healthz` returns `ok`;
- local Palace `/healthz` returns `ok`;
- local Palace `/api/graph` returns parseable graph JSON;
- the MCP tool reports `verification.verdict=verified` and `status=ready`.

## 6. Next Slice

After SSB-12, the strongest remaining conformance gap is not another local
service probe. It is a true Windows UIA runtime adapter or a cross-platform
adapter harness that can exercise Windows UIA on a Windows host.
