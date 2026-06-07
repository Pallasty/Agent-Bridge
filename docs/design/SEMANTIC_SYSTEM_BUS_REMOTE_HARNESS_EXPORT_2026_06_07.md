# Semantic System Bus Remote Harness Export

**Status:** SSB-14 remote harness export
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Previous slice:** [Semantic System Bus Runtime Conformance](SEMANTIC_SYSTEM_BUS_RUNTIME_CONFORMANCE_2026_06_07.md)

## 0. Purpose

SSB-14 exposes the local runtime conformance snapshot through daemon-http:

```text
GET /semantic-bus/runtime-conformance
```

This is not the Windows UIA adapter itself. It is the remote export surface that
lets another Agent-Bridge node publish the same conformance shape over the
existing tailnet-reachable HTTP substrate. Once a Windows host is available, it
can serve its own conformance snapshot without requiring Codex to SSH in or
scrape UI.

## 1. HTTP Surface

Endpoint:

```text
GET /semantic-bus/runtime-conformance
```

Response schema:

```text
agent_bridge.semantic_bus.runtime_conformance.v0
```

Query parameters:

- `cwd`: optional Agent-Bridge repo root for source-backed adapter evidence.
- `include_runtime_health`: defaults to true.
- `daemon_http_url`: base URL for daemon-http health when runtime health is on.
- `palace_url`: base URL for Palace health/graph when runtime health is on.
- `timeout_ms`: bounded per-request timeout for runtime health checks.

## 2. Safety Contract

The endpoint is read-only. It composes the same payload as the MCP tool
`semantic_bus_runtime_conformance`.

It never:

- starts or restarts daemon-http;
- starts or restarts Palace;
- injects desktop input;
- captures screenshots;
- mutates Palace;
- writes memory records or graph edges.

## 3. Why This Comes Before Windows UIA Runtime

The current node is macOS. Implementing Windows UIA runtime evidence locally
would be fake. The remote harness export gives us the correct cross-node shape:

```text
Codex on node A -> daemon-http on node B -> node B conformance snapshot
```

That lets a Windows node eventually report:

- UIA snapshot runtime evidence;
- UIA verify runtime evidence;
- local daemon/Palace health;
- remaining fixture/design gaps.

## 4. Acceptance

Source acceptance:

- daemon-http routes `GET /semantic-bus/runtime-conformance`;
- endpoint returns `agent_bridge.semantic_bus.runtime_conformance.v0`;
- endpoint can be called with `include_runtime_health=false` in tests without
  requiring live services;
- roadmap records this as SSB-14 remote harness export.

Runtime acceptance:

- after deploying and restarting daemon-http, `curl` against the endpoint returns
  the conformance schema;
- local runtime health is `ready` when daemon-http and Palace are available;
- Windows UIA remains explicit as planned until a Windows host provides runtime
  evidence.

## 5. Next Slice

SSB-15 adds the MCP-side peer query helper:

```text
semantic_bus_peer_conformance -> peer /semantic-bus/runtime-conformance
```

After that, SSB-16 should be one of:

- run the remote harness export on a Windows host and add Windows UIA evidence;
- add peer discovery from Agent-Bridge presence rows so agents can find likely
  daemon-http endpoints without manual URLs.
