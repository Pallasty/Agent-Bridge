# Semantic System Bus macOS AX Verify

**Status:** SSB-10 read-only verifier
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

SSB-10 adds the verify leg for the local macOS Accessibility feasibility path.

SSB-9 proved that this Mac can read:

```text
AX trust state + frontmost app + bounded frontmost-app windows
```

SSB-10 turns that into a read-only postcondition checker:

```text
observe macOS AX/System Events state -> check one predicate -> verdict/recover
```

This is the macOS counterpart to `desktop_verify`, but intentionally narrower.

## 1. Tool

The new MCP tool is:

```text
macos_ax_verify
```

It wraps:

```text
scripts/macos_ax_verify.py
```

Default source schema:

```text
macos_ax_verify/v0
```

Opt-in semantic schema:

```text
semantic_bus=true -> agent_bridge.semantic_bus.macos_ax_verify.v0
```

## 2. Safety Boundary

The verifier is read-only.

It does not:

- prompt for Accessibility permission;
- call `AXIsProcessTrustedWithOptions` with the prompt option;
- click, type, focus, activate, resize, move, close, or reorder windows;
- create a persistent service;
- write screenshots or desktop artifacts.

It imports the same read-only helpers as `macos_ax_probe.py`:

```text
AXIsProcessTrusted()
System Events / JXA frontmost app and windows
```

## 3. Expectations

Supported expectations:

```text
ax_trusted_is
frontmost_app_is
window_appeared
window_gone
window_focused
```

Selectors:

```text
app
bundle_id
pid
title
role
index
state
```

Rules:

- `ax_trusted_is` uses `state=true|false`;
- `frontmost_app_is` matches frontmost app by name, bundle id, and/or pid;
- window expectations inspect only the bounded windows of the frontmost app;
- string selectors use case-insensitive substring matching;
- `window_focused` requires a matching window with `AXFocused == true`.

## 4. Output

`macos_ax_verify/v0` returns:

```text
schema
ts
expect
selector
scope
verdict
recover
change
held_after_ms
polls
observed
error
```

`verdict` is one of:

```text
verified
unmet
error
```

`recover` uses the shared vocabulary:

```text
proceed
retry
replan
escalate
```

## 5. Semantic Envelope

When `semantic_bus=true`, the wrapper emits:

```text
agent_bridge.semantic_bus.macos_ax_verify.v0
```

The normalizer maps the verification target into:

```text
object_type = desktop.verify.target.<family>
source_adapter = macos.ax.verify
```

Target families:

```text
permission
application
window
target
```

The envelope emits:

- one semantic object;
- one low-risk reverify affordance;
- one `desktop.verify.completed` event;
- one verification block preserving the lower-layer source verdict;
- one presentation block with compact machine evidence.

## 6. Verification Semantics

The semantic wrapper does not upgrade failed source evidence.

Mapping:

```text
source verdict verified -> semantic verdict verified
source verdict unmet    -> semantic verdict not_verified
source verdict error    -> semantic verdict error
bad source schema       -> semantic verdict not_verified
```

`verified_to=postcondition` is emitted only for verified source verdicts.

## 7. Codex Exposure

`macos_ax_verify` is Standard tier and directly exposed in `codex-essential`
because it is:

- read-only;
- bounded;
- non-prompting;
- the verify half of the macOS semantic desktop path.

## 8. Tests

Focused tests:

```text
cargo test -p ab-bridge macos_ax_verify -- --nocapture
```

They verify:

- Codex essential exposes the tool and schema;
- wrapper args stay bounded and non-mutating;
- non-zero `unmet` script exits still parse as structured JSON;
- default output remains `macos_ax_verify/v0`;
- `semantic_bus=true` returns the semantic envelope;
- raw payload inclusion is opt-in.

## 9. Next Slice

The next useful slice is a conformance report that compares:

```text
desktop_snapshot / desktop_verify
macos_ax_probe / macos_ax_verify
vision_grounding_ocr
Palace / daemon-http state
```

This would show which semantic bus adapters are runtime-backed, fixture-backed,
or still design-only.
