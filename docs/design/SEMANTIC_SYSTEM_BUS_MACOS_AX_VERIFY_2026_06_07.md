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

It does not intentionally:

- request Accessibility permission;
- call `AXIsProcessTrustedWithOptions` with the prompt option;
- click, type, focus, activate, resize, move, close, or reorder windows;
- create a persistent service;
- write screenshots or desktop artifacts.

It imports the same read-only helpers as `macos_ax_probe.py`:

```text
AXIsProcessTrusted()
System Events / JXA frontmost app and windows
```

Before launching `osascript`, the shared probe runs
`AEDeterminePermissionToAutomateTarget` for `com.apple.systemevents` with
`askUserIfNeeded=false`. Only an explicit allowed result proceeds; denied,
would-prompt, unavailable, target-not-running, and unknown results fail closed.
This is a best-effort no-ask preflight. Because the preflight process and the
`osascript` sender are distinct, installed daemon and launchd identities still
require a real-Mac smoke test before claiming a hard no-dialog guarantee.

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
ax_identifier
state
```

Rules:

- `ax_trusted_is` uses `state=true|false`;
- `frontmost_app_is` matches frontmost app by name, bundle id, and/or pid;
- `frontmost_app_is` requires at least one app selector;
- every window expectation requires an exact frontmost-process scope via
  positive `pid` or exact, case-insensitive `bundle_id`, plus a title, role, or
  AXIdentifier window selector;
- app name, window title, and role use case-insensitive substring matching;
  bundle id is exact case-insensitive and AXIdentifier is exact case-sensitive;
- sampling-local `index` may only refine appeared/focused checks, is never a
  sufficient selector, and is rejected for `window_gone`;
- `window_focused` requires a matching window with `AXFocused == true`.

Window comparison is three-state internally: match, no-match, or unknown.
Unknown fields never prove absence. A seen positive witness can prove
`window_appeared` or `window_focused` even when a bounded tail is truncated;
`window_gone` is verified only when enumeration is readable, error-free,
untruncated, count-consistent, app-scoped, and contains no unknown candidate.

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

The v0 verdict vocabulary remains three-valued for compatibility. Evidence
that is internally indeterminate is emitted as `verdict=error` with a typed
`error`, `recover=replan|escalate`, and additive observed evidence:

```text
windows_read_ok
app_identity_valid
window_count / source_window_count / counts_consistent
scope_match
limits.truncated
coverage.complete / coverage.reasons
proof.complete / proof.truth / proof.required_evidence
unknown_count / unknowns
```

Only `verdict=verified` may carry `recover=proceed`.

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
source verdict verified + bound request + admissible proof -> semantic verdict verified
source verdict unmet    -> semantic verdict not_verified
source verdict error    -> semantic verdict error
bad source schema       -> semantic verdict not_verified
```

The wrapper binds the echoed `expect`, selectors, and effective window bound to
the MCP request and checks the source verdict/exit-code pair. The semantic
normalizer then independently checks the claim-specific evidence. In
particular, `window_gone` requires complete coverage, zero unknown candidates,
valid app identity, readable windows, consistent counts, and no truncation.
`verified_to=postcondition` is emitted only after all gates pass.

## 7. Codex Exposure

`macos_ax_verify` is Standard tier and directly exposed in `codex-essential`
because it is:

- read-only;
- bounded;
- preflight-gated, with no explicit permission request;
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
- verdict/exit mismatches and request/response selector drift fail closed;
- malformed selectors, unknown AX fields, wrong app scope, unreadable windows,
  and truncated absence never verify;
- positive truncated witnesses remain admissible;
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
