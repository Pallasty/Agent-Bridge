# Semantic System Bus Desktop Snapshot Runtime Normalization

**Status:** SSB-5 read-only runtime normalization pilot
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

This slice turns SSB-4's fixture-backed Linux desktop conformance into a narrow
runtime proof.

The existing `desktop_snapshot` tool still defaults to its current behavior:

```text
desktop_snapshot/v0.5
```

SSB-5 adds an opt-in compatibility wrapper:

```text
semantic_bus=true -> agent_bridge.semantic_bus.desktop_snapshot.v0
```

The wrapper is read-only. It does not click, type, move windows, activate global
accessibility, write screenshots unless the existing screenshot flag requests
that, or expose any new action path.

## 1. New Arguments

`desktop_snapshot` now accepts:

```text
semantic_bus: boolean = false
semantic_include_raw: boolean = false
```

Compatibility rule:

- `semantic_bus=false` preserves the current output shape, apart from the
  existing `mcp_wrapper` metadata already added by Agent-Bridge.
- `semantic_bus=true` returns the semantic bus envelope.
- `semantic_include_raw=true` embeds the original wrapped
  `desktop_snapshot/v0.5` payload as `raw_snapshot`.
- `semantic_include_raw=false` keeps the semantic envelope compact while still
  marking `raw_available=true`.

## 2. Semantic Envelope

The runtime schema is:

```text
agent_bridge.semantic_bus.desktop_snapshot.v0
```

Top-level fields:

```text
schema
source_schema
source_adapter
captured_at
read_only
raw_available
raw_included
semantic_objects
affordances
events
verification
presentation
raw_snapshot
```

`raw_snapshot` is present only when requested.

## 3. Object Mapping

The normalizer emits three families:

### Session Object

```text
object_type = desktop.session
source_adapter = linux.sway.session
```

The session object anchors the capture timestamp, compositor/session metadata,
window count, and screenshot posture.

### Window Objects

```text
object_type = desktop.window
source_adapter = linux.sway.tree
```

Each sway window becomes a semantic object with app id, title, pid, focus,
visibility, geometry, output, and grounding metadata. Each window gets a
read-only `desktop.verify` affordance.

### AT-SPI Objects

```text
object_type = desktop.accessible.<role>
source_adapter = linux.atspi
```

Each AT-SPI element becomes a semantic object linked back to the session and,
when possible, to the containing sway window by pid. Every element gets a
read-only `desktop.verify` affordance. Actionable roles also expose a gated
`desktop.invoke` affordance as metadata only.

Important boundary:

```text
desktop.invoke requires_gate=true
```

The snapshot wrapper describes possible action surfaces but does not expose or
perform those actions.

## 4. Verification

The wrapper reports:

```text
verification.method = desktop_snapshot.semantic_normalizer
verification.verdict = verified
verification.verified_to = semantic_objects
verification.recover = proceed
```

This means only that the parsed `desktop_snapshot/v0.5` payload was normalized
into semantic objects. It does not claim that every pixel was rendered, every
app has an accessibility tree, or that a later action would succeed.

If the source schema is unexpected, the wrapper returns:

```text
verification.verdict = not_verified
verification.reason = unexpected_source_schema
verification.recover = replan
```

## 5. Events And Presentation

The wrapper emits one lightweight observation event:

```text
desktop.snapshot.observed
```

The presentation block summarizes object, affordance, window, and AT-SPI object
counts. Ingestion remains blocked:

```text
ingestion.allowed = false
ingestion.reason = runtime_snapshot_not_durable_memory
```

Runtime desktop state should not be written into durable memory merely because a
tool observed it.

## 6. Tests

Focused tests:

```text
cargo test -p ab-bridge desktop_snapshot_wrapper_defaults_to_non_mutating_script_flags -- --nocapture
cargo test -p ab-bridge desktop_snapshot_semantic_bus -- --nocapture
```

The new semantic test verifies:

- default `desktop_snapshot` output stays `desktop_snapshot/v0.5`;
- `semantic_bus=true` returns `agent_bridge.semantic_bus.desktop_snapshot.v0`;
- raw snapshot is omitted unless `semantic_include_raw=true`;
- session, sway window, and AT-SPI objects are emitted;
- read-only `desktop.verify` affordances are ungated;
- `desktop.invoke` affordances remain gated metadata;
- presentation and event blocks are populated.

## 7. Next Slice

The next useful step is one of:

1. add a similar opt-in semantic wrapper for `desktop_verify`; or
2. write the cross-platform mapping memo for macOS AX and Windows UIA.

The `desktop_verify` wrapper is the stronger implementation proof. The mapping
memo is better if another agent is working on platform coverage.
