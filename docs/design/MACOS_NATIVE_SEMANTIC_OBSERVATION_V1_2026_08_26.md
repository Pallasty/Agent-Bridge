# macOS Native Semantic Observation v1

Status: implementation candidate

Date: 2026-08-26

## Product problem

The deployed macOS observation path has Accessibility trust but asks System
Events through Apple Events/JXA for window state. A stopped or unapproved
System Events target therefore makes ordinary read-only observation degraded,
even though the same frontmost application and its AX windows are directly
readable through `NSWorkspace` and `AXUIElement`.

This costs the beneficiary a usable semantic desktop sample and forces a
slower screenshot or manual-description fallback. It also conflates two
different facts: whether the current sample was observed completely and
whether a window exposes an identity safe to reuse in a later action.

## Increment

1. Make the native `NSWorkspace` plus `AXUIElement` sampler the default Darwin
   backend for `macos_ax_probe`, `macos_ax_watch`, and `macos_ax_verify`.
   Observation must not use System Events, Apple Events, screenshots, OCR, or
   setters.
2. Report sample observation separately from stable identity:
   - a complete app/window sample remains complete when `AXIdentifier` is
     missing;
   - a unique non-empty `AXIdentifier` is the only stable window identity;
   - missing or duplicate identifiers remain ineligible for continuity and
     action admission.
3. Bind every sample-local semantic object id to the exact sample id. Never
   infer appeared, disappeared, or focus lifecycle for sample-local windows.
4. Treat one sample as an atomic frontmost-process observation: re-read the
   frontmost process after window enumeration and reject the sample if its PID
   changed while the sample was being assembled.

## Compatibility and authority

- Preserve the existing `macos_ax_probe/v0`, `macos_ax_watch/v0`, and
  `macos_ax_verify/v0` entry points and bounded CLI arguments.
- New fields are additive. Existing `coverage_complete` remains the sample
  coverage compatibility field.
- Existing focus/action admission remains fail-closed on exact PID, bundle id,
  and a sample-unique non-empty `AXIdentifier`.
- A verified focus receipt is bound to the exact audited native sampler,
  Python helper, and developer toolchain paths; missing, changed, or tampered
  runtime binding produces an unknown outcome rather than a green receipt.
- This increment grants no new mutation, permission-prompt, screenshot,
  coordinate, text-injection, app-activation, scheduler, or service authority.

## Acceptance

- A live frontmost Codex/ChatGPT window without `AXIdentifier` returns a ready,
  complete native sample with app identity, window count, title, role, focus
  state, and `stable_identity_available=false`.
- Two complete samples produce state fingerprints and a drift decision, while
  emitting no sample-local window lifecycle event.
- Two samples give the same sample-local window different object ids.
- A unique `AXIdentifier` remains stable and action-eligible; missing or
  duplicate identifiers remain action-ineligible.
- Truncated, malformed, untrusted, or failed AX reads still fail closed.
- A frontmost-process transition during enumeration fails closed instead of
  returning a mixed app/window sample.
- Deployment tests prove the native sampler is installed beside the Python
  runtime assets. Fresh-MCP acceptance is a later deployment gate.

## Benefit measure

For one natural frontmost-app task on this Mac, the beneficiary should obtain a
verified semantic sample and usable next-step decision without screenshots,
Apple Events permission state, or owner restatement. If the native path cannot
do that within this increment, stop rather than opening another observation
framework.
