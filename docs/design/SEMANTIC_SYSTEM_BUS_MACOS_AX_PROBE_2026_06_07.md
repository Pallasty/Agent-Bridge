# Semantic System Bus macOS AX Probe

**Status:** SSB-9 read-only feasibility probe
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

SSB-9 adds the first local macOS runtime probe for the semantic system bus.

The goal is intentionally narrow:

```text
macOS Accessibility trust + frontmost app/window summary -> semantic bus envelope
```

It is not a macOS desktop action layer. It is a feasibility probe that tells an
agent whether the local Mac already exposes enough AX state to become a future
adapter.

## 1. Tool

The new MCP tool is:

```text
macos_ax_probe
```

It wraps:

```text
scripts/macos_ax_probe.py
```

Default source schema:

```text
macos_ax_probe/v0
```

Opt-in semantic schema:

```text
semantic_bus=true -> agent_bridge.semantic_bus.macos_ax_probe.v0
```

## 2. Safety Boundary

The probe is read-only.

It does not:

- prompt for Accessibility permission;
- call `AXIsProcessTrustedWithOptions` with the prompt option;
- click, type, focus, activate, resize, move, or close windows;
- create a persistent service;
- write screenshots or desktop artifacts.

The script first calls:

```text
AXIsProcessTrusted()
```

If AX is not already trusted, it reports:

```text
status = degraded
permission.prompted = false
```

and skips System Events window reads.

Before launching `osascript`, the probe calls
`AEDeterminePermissionToAutomateTarget` for System Events with
`askUserIfNeeded=false`. Every result other than explicit permission is a typed
failure and prevents the Apple Event send. This is a best-effort prompt guard,
not a platform-level proof: the preflight runs in Python while the eventual
sender is `osascript`, so sender attribution and UI behavior must also pass the
installed-path Mac acceptance test.

If System Events is not already running, macOS returns `procNotFound` (`-600`)
and the probe fails closed rather than launching it. Starting System Events is
therefore an operator-owned acceptance prerequisite, not a side effect of this
read-only adapter.

## 3. Arguments

```text
include_windows: boolean = true
max_windows: integer = 8
jxa_timeout_secs: number = 4.0
semantic_bus: boolean = false
semantic_include_raw: boolean = false
timeout_ms: integer = 8000
```

`include_windows=false` keeps the probe to platform and permission state only.

`include_windows=true` reads frontmost app/window metadata through System
Events only when Accessibility is already trusted.

For a window read, the Rust wrapper raises the effective process timeout when
needed so it is never shorter than `jxa_timeout_secs` plus three seconds for
Python startup, the no-ask Automation preflight, and result serialization.
This keeps the outer watchdog from preempting a valid inner JXA timeout. With
`include_windows=false`, the requested `timeout_ms` remains unchanged.

## 4. Probe Payload

`macos_ax_probe/v0` returns:

```text
schema
captured_at
platform
read_only
status
permission
frontmost_app
windows
window_count
source_window_count
limits
errors
elapsed_ms
```

`status` is one of:

```text
ready
degraded
unsupported_platform
```

`degraded` is a normal result. It usually means the process is not AX-trusted
or System Events could not read the frontmost app within the bounded timeout.

## 5. Semantic Envelope

When `semantic_bus=true`, the wrapper emits:

```text
agent_bridge.semantic_bus.macos_ax_probe.v0
```

The normalizer maps:

- session -> `desktop.session` with `source_adapter = macos.ax_probe`;
- frontmost app -> `desktop.application` with `source_adapter = macos.system_events`;
- windows -> `desktop.window` with `source_adapter = macos.ax.window`.

Window objects get one low-risk reobserve affordance:

```text
action_type = macos_ax_probe.reobserve
requires_gate = false
```

This affordance reruns the same read-only probe. It is not a mutation path.

## 6. Verification

The semantic wrapper verifies only the normalization boundary.

For `ready` and `degraded` source payloads:

```text
verification.verdict = verified
verification.verified_to = semantic_objects
verification.recover = proceed
```

For non-macOS:

```text
verification.verdict = blocked
verification.reason = unsupported_platform
verification.recover = replan
```

For unexpected source schema:

```text
verification.verdict = not_verified
verification.reason = unexpected_source_schema
verification.recover = replan
```

## 7. Codex Exposure

`macos_ax_probe` is a Standard-tier tool and is directly exposed in the
`codex-essential` allowlist because it is:

- read-only;
- bounded;
- guarded by a best-effort no-ask Apple Events preflight and fail-closed when
  permission is not already explicit;
- useful for deciding whether semantic desktop state is available on macOS.

## 8. Tests

Focused tests:

```text
cargo test -p ab-bridge macos_ax_probe -- --nocapture
```

They verify:

- Codex essential exposes the tool and schema;
- the wrapper passes bounded arguments and the script gates System Events with
  a no-ask Automation preflight;
- default output remains `macos_ax_probe/v0`;
- `semantic_bus=true` returns the semantic envelope;
- raw payload inclusion is opt-in.

## 9. Next Slice

The next useful slice is one of:

1. add a macOS verify probe that checks one selector/window predicate without
   mutation; or
2. add a daemon/Palace adapter-conformance report so desktop probes, memory
   graph state, and observatory surfaces can be compared in one place.
