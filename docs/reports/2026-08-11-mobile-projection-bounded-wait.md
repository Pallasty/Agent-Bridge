# Mobile Projection Bounded Wait — 2026-08-11

## Outcome

`mobile_projection_wait` removes manual status polling from the normal mobile
projection workflow. It waits for one of two authenticated observations:

- the first successful device pull, which is evidence that consent was granted;
- delivery of a caller-selected frame revision.

The wait is read-only and bounded to 100–120,000 milliseconds. It does not
reopen the Android Activity, extend the projection TTL, start a service, or add
authority. A timeout is reported as `timeout_without_matching_evidence`; it is
not interpreted as rejection or an explicit disconnect.

Stopped and expired sessions return terminal factual outcomes immediately.
Requests for a revision newer than the current host frame fail fast instead of
waiting for an impossible condition.

## Validation

- `cargo check -p ab-bridge --lib`
- Codex essential allowlist test passed
- wait observation/terminal-state unit test passed
- source formatting checked for the changed sections
- existing compiler warnings are unrelated to this change
