# Mobile Projection Lifecycle Tools — 2026-08-11

## Outcome

Agent-Bridge can now observe and stop a consent-driven Android projection
session instead of treating start as a fire-and-forget operation.

## Implemented

- `mobile_projection_status` reports recent or selected in-process sessions.
- `mobile_projection_stop` stops the listener and force-stops the companion.
- A new start stops older listeners for the same device serial.
- Session retention is bounded; one MCP process cannot accumulate listeners
  indefinitely.
- Status distinguishes recent authenticated polling from later inactivity and
  never presents inactivity as proof of an explicit disconnect.

## Physical-device evidence

- Device serial: `3K661F0178H00000`
- Session: `mcp-1786457440-77bdee41b73f`
- Endpoint: `192.168.1.16:45193`
- The holder manually pressed **Allow and connect**.
- Status then reported `connected_recently`, `consent_observed=true`, and 11
  authenticated pulls while the listener remained active.
- Before stop completed, the listener had observed 16 pulls.
- Stop returned ADB exit code 0 and status subsequently reported
  `phase=stopped`, `listener_active=false`, `stop_requested=true`, and
  `ended=true`.
- `CompanionService` was never started. After stop, both the package process
  probe and service probe were empty.

## Validation

- `cargo check -p ab-bridge --lib`
- `cargo test -p ab-bridge 'mobile_' --lib` — 18 passed
- lifecycle phase unit test — passed
- live start → consent → status → stop → status sequence — passed
