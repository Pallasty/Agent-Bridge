# Semantic System Bus Desktop Verify Runtime Normalization

**Status:** SSB-6 read-only runtime normalization pilot
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

This slice normalizes `desktop_verify` after SSB-5 normalized
`desktop_snapshot`.

`desktop_snapshot` can now expose read-only `desktop.verify` affordances. SSB-6
normalizes the verifier result itself so an agent can consume one semantic
answer:

```text
postcondition target -> verification event -> recover hint
```

The existing `desktop_verify` tool still defaults to its current behavior:

```text
desktop_verify/v0
```

SSB-6 adds an opt-in compatibility wrapper:

```text
semantic_bus=true -> agent_bridge.semantic_bus.desktop_verify.v0
```

The wrapper is read-only. It does not click, type, move windows, activate global
accessibility, or mutate Agent-Bridge state. It only re-observes the same bus
surfaces that `desktop_verify.py` already reads.

## 1. New Arguments

`desktop_verify` now accepts:

```text
semantic_bus: boolean = false
semantic_include_raw: boolean = false
```

Compatibility rule:

- `semantic_bus=false` preserves the current output shape, apart from the
  existing `mcp_wrapper` metadata already added by Agent-Bridge.
- `semantic_bus=true` returns the semantic bus envelope.
- `semantic_include_raw=true` embeds the original wrapped
  `desktop_verify/v0` payload as `raw_verify`.
- `semantic_include_raw=false` keeps the semantic envelope compact while still
  marking `raw_available=true`.

## 2. Semantic Envelope

The runtime schema is:

```text
agent_bridge.semantic_bus.desktop_verify.v0
```

Top-level fields:

```text
schema
source_schema
source_adapter
observed_at
read_only
raw_available
raw_included
semantic_objects
affordances
events
verification
presentation
raw_verify
```

`raw_verify` is present only when requested.

## 3. Object Mapping

The normalizer emits one semantic target object per verifier result:

```text
object_type = desktop.verify.target.accessible
object_type = desktop.verify.target.window
```

The family is derived from `expect`:

- `element_gone`, `element_appeared`, `state_is`, and `state_not` map to
  `accessible`;
- `window_gone`, `window_appeared`, and `focus_is` map to `window`.

The target object carries the source selector, scope, observed evidence, source
verdict, recover hint, poll count, `held_after_ms`, and source error if one was
reported.

## 4. Affordance Mapping

Each target object gets one ungated read-only affordance:

```text
action_type = desktop.verify
requires_gate = false
risk_level = low
```

This is a reverify affordance, not an action affordance. It describes how to
repeat the same postcondition check without mutating the desktop.

## 5. Verification

The wrapper maps source verdicts as follows:

```text
desktop_verify verified -> verification.verdict = verified
desktop_verify unmet    -> verification.verdict = not_verified
desktop_verify error    -> verification.verdict = error
```

The source `recover` hint is preserved:

```text
proceed | retry | replan | escalate
```

If the source schema is unexpected, the wrapper returns:

```text
verification.verdict = not_verified
verification.reason = unexpected_source_schema
verification.recover = replan
```

`verified_to=postcondition` is set only when the source verifier returned
`verified`.

## 6. Events And Presentation

The wrapper emits one event:

```text
desktop.verify.completed
```

The event payload carries `expect`, source verdict, recover hint, change
classification, observed count, held time, and poll count.

The presentation block summarizes:

```text
desktop_verify <expect> returned <verdict>; recover=<recover>
```

Runtime verifier results are not durable memory by default:

```text
ingestion.allowed = false
ingestion.reason = runtime_verify_not_durable_memory
```

## 7. Tests

Focused tests:

```text
cargo test -p ab-bridge desktop_verify -- --nocapture
```

The new semantic test verifies:

- default `desktop_verify` output stays `desktop_verify/v0`;
- `semantic_bus=true` returns `agent_bridge.semantic_bus.desktop_verify.v0`;
- raw verify output is omitted unless `semantic_include_raw=true`;
- source verdict, recover hint, observed count, event, presentation, and
  reverify affordance are populated;
- the reverify affordance remains read-only and ungated.

## 8. Next Slice

The next useful step is a cross-platform mapping memo for macOS AX and Windows
UIA. The memo should map platform-specific accessible/window primitives into the
same SSB object, affordance, event, and verification vocabulary instead of
fragmenting the schema.
