# Semantic System Bus Linux Adapter Conformance

**Status:** SSB-4 fixture-backed conformance pilot
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

This slice makes Linux the first OS reference substrate for Semantic System Bus
adapter behavior.

SSB-4 is intentionally fixture-backed. It does not rewrite desktop runtime
tools. Instead, it pins what the Linux desktop/process adapters must preserve
when their outputs are normalized into the semantic bus:

```text
desktop_snapshot -> desktop_verify -> vision_grounding_ocr fallback
process/daemon health -> service semantic object
```

The core product decision remains:

```text
semantic bus first, pixels as fallback
```

## 1. New Contract

Fixtures can now carry:

```text
agent_bridge.semantic_bus.adapter_conformance.v0
```

Current fields:

```text
schema
adapter_family
tool
read_only
broad_host_mutation
mutation_surface
channels
fallback_order
fallback_for
isolation
notes
```

The conformance test currently asserts:

- accepted tools are `desktop_snapshot`, `desktop_verify`,
  `vision_grounding_ocr`, and `daemon_http`;
- all SSB-4 fixtures are read-only;
- all SSB-4 fixtures set `broad_host_mutation=false`;
- all SSB-4 fixtures set `mutation_surface=none`;
- Linux desktop fixtures use `source_adapter` values under `linux.*`;
- `desktop_snapshot` and `desktop_verify` keep OCR as fallback, not primary
  semantic state;
- `vision_grounding_ocr` declares which semantic surfaces it is a fallback for;
- coordinate actions exposed by OCR fixtures must require a gate;
- recover hints stay inside the desktop verify vocabulary:
  `proceed`, `retry`, `replan`, `escalate`.

## 2. Fixture Pack

New fixtures:

```text
crates/bridge/fixtures/semantic_bus/linux_desktop_snapshot_state.json
crates/bridge/fixtures/semantic_bus/linux_desktop_verify_postcondition.json
crates/bridge/fixtures/semantic_bus/linux_vision_grounding_ocr_fallback.json
```

Updated fixture:

```text
crates/bridge/fixtures/semantic_bus/daemon_http_service.json
```

### desktop_snapshot

`linux_desktop_snapshot_state` represents a semantic desktop window object from
the compositor and AT-SPI layers:

```text
source_adapter = linux.sway.atspi
channels = sway_tree + atspi
fallback_order = sway_tree -> atspi -> vision_grounding_ocr
```

This encodes that the desktop state tree is the primary readable surface. Pixels
are only a fallback when the bus/tree cannot answer.

### desktop_verify

`linux_desktop_verify_postcondition` represents a read-only postcondition check:

```text
source_adapter = linux.atspi.verify
method = desktop_verify.polling_atspi
recover = proceed
```

The important contract is that verification reuses the selector and returns one
of the direct recover hints. A caller should not need to infer next action from
a full fresh screenshot.

### vision_grounding_ocr

`linux_vision_grounding_ocr_fallback` represents OCR as fallback grounding:

```text
source_adapter = linux.vision.ocr
verdict = not_verified
recover = replan
```

OCR may find useful coordinates, but this fixture deliberately does not treat
OCR as semantic verification. Its coordinate-click affordance is high-risk and
`requires_gate=true`.

### daemon_http

`daemon_http_service` now carries a process/daemon conformance block:

```text
adapter_family = process_daemon
tool = daemon_http
channels = http_health + process_state
isolation = localhost_only
```

This keeps service health in the same semantic bus family without pretending it
is a Linux desktop widget.

## 3. Boundaries

- No runtime behavior changes to desktop tools.
- No new host mutation.
- No new MCP tool exposure.
- No screenshots as primary state.
- No macOS AX or Windows UIA mapping yet.

## 4. Verification

Focused contract test:

```text
cargo test -p ab-bridge --test semantic_bus_fixtures -- --nocapture
```

The test now validates both:

- the original minimum semantic fixture contract; and
- SSB-4 Linux adapter conformance rules.

## 5. Next Slice

After SSB-4, the next useful implementation is a narrow runtime normalization
helper for one read-only desktop tool, preferably `desktop_snapshot`.

Recommended SSB-5 candidate:

```text
desktop_snapshot -> agent_bridge.semantic_bus.desktop_snapshot.v0
```

Keep it read-only. The helper should produce stable object IDs, source adapter
names, affordance hints, and verification metadata without changing existing
`desktop_snapshot/v0.5` output.
