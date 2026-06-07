# Semantic System Bus Peer Conformance Query

**Status:** SSB-15 peer query slice
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Previous slice:** [Semantic System Bus Remote Harness Export](SEMANTIC_SYSTEM_BUS_REMOTE_HARNESS_EXPORT_2026_06_07.md)

## 0. Purpose

SSB-15 adds an MCP-side query helper for remote Semantic System Bus runtime
conformance exports.

SSB-14 made each daemon-http node able to publish:

```text
GET /semantic-bus/runtime-conformance
```

SSB-15 lets an agent ask one or more nodes for that shape and receive a compact
multi-peer summary. This is the bridge between a local Codex session and future
Windows/aio nodes that can report their own UIA or platform-specific evidence.

## 1. MCP Surface

Tool:

```text
semantic_bus_peer_conformance
```

Response schema:

```text
agent_bridge.semantic_bus.peer_conformance.v0
```

Inputs:

- `endpoints`: array of daemon-http base URLs, or full
  `/semantic-bus/runtime-conformance` URLs.
- `endpoint`: single-endpoint compatibility shortcut.
- `include_runtime_health`: asks each peer to include its local runtime health
  summary.
- `timeout_ms`: bounded per-peer HTTP timeout.
- `include_raw`: optional raw peer payload inclusion; default false keeps the
  result compact.

Each peer row summarizes:

- endpoint and URL;
- HTTP/status/error state;
- conformance schema and verdict;
- runtime health status;
- adapter count and live-ready count;
- Windows UIA runtime slot state.

## 2. Safety Contract

The peer query helper only performs bounded HTTP GET requests against supplied
daemon-http endpoints.

It never:

- starts or restarts services;
- captures screenshots;
- injects desktop input;
- mutates Palace;
- writes memory records or graph edges;
- assumes Windows UIA evidence exists when a peer does not report it.

## 3. Why This Comes Before Windows UIA Runtime

The current node is macOS, so local Windows UIA evidence would be fake. The peer
query shape lets a Windows node later prove its own runtime state while Codex can
stay on the orchestrating node:

```text
Codex MCP -> semantic_bus_peer_conformance -> daemon-http peer export
```

Once a Windows host reports a `ready` Windows UIA runtime slot, the next slice
can validate actual snapshot/verify payload semantics rather than only transport
reachability.

## 4. Acceptance

Source acceptance:

- `semantic_bus_peer_conformance` is registered in the MCP registry.
- The tool is included in Codex essential direct extras.
- Unit tests verify URL construction, compact peer summary, no-endpoint
  behavior, and registry exposure.
- Roadmap records SSB-15 as peer conformance query.

Runtime acceptance:

- after deploy and MCP reconnect, current Codex exposes the tool;
- querying local `http://127.0.0.1:7878` returns
  `agent_bridge.semantic_bus.peer_conformance.v0`;
- local peer row reports the nested runtime conformance schema
  `agent_bridge.semantic_bus.runtime_conformance.v0`;
- Windows UIA remains explicit until a Windows peer reports runtime evidence.

## 5. Next Slice

SSB-16 should depend on available hardware:

- if a Windows node is available, run the daemon-http export there and validate
  UIA runtime evidence through `semantic_bus_peer_conformance`;
- otherwise, add a small peer-discovery layer from Agent-Bridge presence rows so
  agents can suggest likely daemon-http endpoints without manual URLs.
