# Mobile Projection Intentional Patch — 2026-08-11

## Goal

Make repeated action-card updates concise and safe during real collaboration.
Previously every update had to resend title and body, while omitting status or
actions silently cleared them.

## Contract

`mobile_projection_update` now treats presentation fields as a patch:

- omitted `title`, `body`, `status`, or `actions` preserve the current value;
- `status: null` explicitly clears the status card;
- `actions: null` or `actions: []` explicitly clears the action list;
- title and body accept strings when supplied, including an intentional empty
  string;
- a request containing only `session_id` is rejected and does not create a new
  revision;
- successful responses list `changed_fields`.

The patch does not change the session endpoint, token, expiry, consent,
listener, companion-service state, or zero-authority boundary.

## Validation

- `cargo check -p ab-bridge`
- `cargo test -p ab-bridge 'mobile_' --lib`: 27 passed
- tests cover preservation, explicit clearing, empty patches, and malformed
  field types

## Physical-device acceptance

Validated after deployment on OPPO PKW110, Android 16, session
`mcp-1786511866-1ec4c41c27b5`:

- revision 1 was authenticated and observed by the device;
- a status-only patch produced revision 2 with `changed_fields: ["status"]`;
- revision 2 retained the original 8-character title, 21-character body, and
  two actions;
- an explicit `status: null, actions: []` patch produced revision 3 with both
  fields listed under `changed_fields`;
- revision 3 retained the title/body while reporting no status and zero
  actions;
- Android UIAutomator confirmed the original title/body at revision 3 and no
  remaining status/action nodes;
- both updates kept the TTL, Activity, companion-service state, and authority
  boundary unchanged;
- the session was explicitly stopped and ADB force-stop returned exit code 0.
