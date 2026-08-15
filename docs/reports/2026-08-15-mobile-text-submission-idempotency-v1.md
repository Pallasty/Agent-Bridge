# Mobile text submission idempotency V1

Date: 2026-08-15

## Trigger

The real-device V1 projection acceptance observed two host acceptance events
for an identical two-character draft digest. The existing nonce replay guard
protected an identical transport request, but two foreground submissions used
different nonces and were both recorded.

## Implementation

- advanced the text-observation schema to
  `agent_bridge.mobile_text_observation.v1`;
- added a required 128-bit lowercase-hex `submission_id` to the authenticated
  payload;
- added session-local host state mapping `submission_id` to payload SHA-256;
- the first valid ID produces `TextSubmitted` and increments the MCP session's
  text-submission count;
- a retry with the same ID and digest receives a fresh authenticated
  acknowledgement but produces `TextSubmissionDeduplicated` and does not
  create or count a second observation;
- reuse of an ID with a different digest is rejected;
- the Android submit button is disabled while a submission is in flight;
- the Android client performs at most one bounded retry, retaining the same
  `submission_id` while refreshing timestamp and nonce;
- draft text is cleared only after an authenticated acknowledgement; otherwise
  it remains editable on the device.

## Verification

- `cargo test -p ab-bridge mobile_projection --lib`: 26 passed, 0 failed;
- the replay test sends the same `submission_id` with a different nonce,
  receives `ACCEPTED` both times, and verifies one accepted observation plus
  one deduplicated event;
- `cargo check -p ab-bridge --bin mobile-projection-host`: PASS;
- `android/agent-bridge-companion/test-protocol.sh`: PASS;
- exact-file `rustfmt --check`: PASS;
- `git diff --check`: PASS.

## Boundary

This is a source-and-test qualification only. No APK was built, signed,
installed, launched, or admitted on the device. A later APK build and device
replacement require their own authorization and evidence.

