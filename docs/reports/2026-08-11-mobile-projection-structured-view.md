# Mobile Projection Structured Action View — 2026-08-11

## Goal

Make a phone projection scannable during real collaboration without turning it
into a remote-control surface.

## Design

The existing v1 authenticated frame remains backward compatible. Two optional
fields were added:

- `status`: one short state label, limited to 80 characters;
- `actions`: up to six ordered display-only actions, each limited to 240
  characters.

Title and body remain required and unchanged. Older clients ignore the new
JSON fields. The Android Activity renders the status separately and formats
actions as a numbered list. It adds no action buttons, callbacks, sensors,
background service, TTL extension, or authority.

Both `mobile_projection_start` and `mobile_projection_update` accept the new
optional fields. Omitting them from an update clears the structured view.

## Validation

- Rust library check and bounded-presentation unit test
- Android pure-Java protocol tests
- signed APK build and Android 16 upgrade install
- physical-device consent, structured revision delivery, UI inspection, and
  explicit stop
