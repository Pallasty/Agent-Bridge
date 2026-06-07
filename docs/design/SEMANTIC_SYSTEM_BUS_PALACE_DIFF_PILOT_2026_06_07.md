# Semantic System Bus Palace Diff Pilot

**Status:** SSB-2 read-only pilot  
**Date:** 2026-06-07  
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

This pilot makes Palace the first user-visible Semantic System Bus surface.

It does not change memory graph behavior, write memory rows, write graph edges,
or mutate the 7979 service state. It only normalizes the existing Palace graph
snapshot into a semantic bus envelope:

```text
Semantic Object -> Event -> Verification -> Presentation
```

The intentionally missing stage is `Action`: SSB-2 is a read-only observation
pilot. Action/result normalization remains SSB-3.

## 1. Endpoint

```text
GET /api/semantic-events
```

Optional query parameters:

```text
all=1
baseline_nodes=N
baseline_edges=N
baseline_orphans=N
baseline_hubs=N
```

`all=1` mirrors `/api/graph?all=1`. Baseline parameters are caller-provided so
the server stays stateless and read-only. The Palace browser UI stores the last
observed counts in `localStorage` and passes them back on the next refresh.
External monitors can do the same without depending on browser state.

## 2. Response Shape

The response schema is:

```text
agent_bridge.semantic_bus.palace_diff.v0
```

Top-level fields:

```text
schema
source_adapter
observed_at
semantic_objects
events
diff
verification
presentation
```

The primary semantic object is:

```text
object_id: palace:memory-graph
object_type: palace.memory_graph
source_adapter: palace.memory_graph
```

The endpoint emits two events:

```text
palace.graph.observed
palace.graph.diff.changed | palace.graph.diff.unchanged
```

The event hashes are read-only, unpersisted hashes over the normalized payload.
They are not yet event-spine hashes and must not be treated as durable replay
anchors.

## 3. Verification Rules

The pilot returns:

```text
verification.verdict = verified
verification.reason = palace_graph_snapshot_normalized
verification.method = server_side_graph_builder
verification.verified_to = semantic_objects/events/diff
verification.raw_available = true
```

This means only that the response was built from the same server-side graph
builder as `/api/graph`. It does not claim that the browser rendered every node,
that the graph is healthy, or that the memory substrate is complete.

## 4. Palace UI

The Palace footer now includes a compact semantic bus pulse:

```text
bus:verified|changed · obj:N · evt:N · dn:+/-N de:+/-N do:+/-N dh:+/-N
```

Where:

- `dn`: node count delta
- `de`: edge count delta
- `do`: orphan count delta
- `dh`: hub count delta

This is intentionally small. Palace remains a graph viewer first; the SSB footer
is evidence that a machine-readable semantic event layer exists beneath it.

## 5. Boundaries

- No memory writes.
- No graph edge writes.
- No event-spine persistence yet.
- No action/result wrapper yet.
- No screenshot or OCR dependency.
- No cross-platform adapter claims.

## 6. Next Slice

After SSB-2, the next implementation slice should be SSB-3:

```text
LSWR action_result wrapper
```

Reason:

- LSWR already has the strongest no-laundering verification discipline.
- SSB-2 covers read-only observation.
- SSB-3 should prove the mutation/query action envelope before Linux desktop
  adapter conformance expands host actions.
