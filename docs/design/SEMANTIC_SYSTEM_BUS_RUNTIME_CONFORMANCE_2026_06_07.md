# Semantic System Bus Runtime Conformance

**Status:** SSB-13 harness pre-slice
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Previous slice:** [Semantic System Bus Runtime Health](SEMANTIC_SYSTEM_BUS_RUNTIME_HEALTH_2026_06_07.md)

## 0. Purpose

SSB-13 adds a compact read-only conformance snapshot for the Semantic System
Bus. It does not implement a Windows UIA runtime adapter locally. Instead it
keeps the Windows slot explicit while aggregating the runtime evidence already
available on this node:

```text
adapter evidence report + local runtime health -> runtime conformance snapshot
```

This is the harness shape we need before adding more platform adapters. It lets
Codex answer:

- Which adapter families are runtime-backed?
- Which are fixture-only?
- Which are design-only?
- Which local runtime surface is live right now?
- Which platform gap should be implemented next?

## 1. MCP Surface

Tool:

```text
semantic_bus_runtime_conformance
```

Schema:

```text
agent_bridge.semantic_bus.runtime_conformance.v0
```

Inputs:

- `cwd`: optional Agent-Bridge repo root for source-backed adapter evidence.
- `include_runtime_health`: run local daemon-http/Palace health checks.
- `daemon_http_url`: defaults to `http://127.0.0.1:7878`.
- `palace_url`: defaults to `http://127.0.0.1:7979`.
- `timeout_ms`: bounded runtime-health timeout.

The tool is exposed to `codex-essential` because it stays compact, read-only,
and provides a high-level decision surface for the next SSB slice.

## 2. Safety Contract

The conformance snapshot itself only composes existing read-only reports:

- `semantic_bus_adapter_report`
- `semantic_bus_runtime_health`

It never:

- starts or restarts services;
- injects desktop input;
- captures screenshots;
- mutates Palace;
- writes memory records or graph edges;
- pretends a platform runtime adapter exists when no runtime host is available.

## 3. Harness Semantics

Each adapter row receives a `live_status`:

- `ready`: live runtime check passed.
- `runtime_backed_available_not_checked`: runtime-backed on the current
  platform, but the harness did not run that specific probe.
- `runtime_backed_not_current_platform`: runtime-backed, but not on this OS.
- `fixture_only`: fixture-backed only.
- `design_only`: planned, with no runtime implementation.

The Windows UIA runtime row remains `design_only` on this macOS node. That is
intentional: SSB should preserve missing runtime evidence rather than collapsing
it into a screenshot fallback or an invented pass.

## 4. Acceptance

Source acceptance:

- `semantic_bus_runtime_conformance` is registered in the MCP registry.
- The tool is included in Codex essential direct extras.
- Unit tests verify registry exposure and no-live-check summarization.
- Roadmap records SSB-13 as a harness pre-slice.

Runtime acceptance:

- current MCP exposes the tool after reconnect;
- live call with `include_runtime_health=true` reports local runtime health as
  `ready` when daemon-http and Palace are healthy;
- Windows UIA remains explicit as unavailable/planned until a Windows host can
  provide runtime evidence.

## 5. Next Slice

The next implementation slice should run on, or dispatch to, a Windows host:

```text
Windows UIA tree + verify predicates -> semantic bus desktop snapshot/verify
```

If no Windows host is available, the next best slice is a remote harness runner
that can ask another Agent-Bridge node to produce the same conformance snapshot.
