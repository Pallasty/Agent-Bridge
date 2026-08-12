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

