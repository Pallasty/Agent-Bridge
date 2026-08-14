# GSL-1C mobile text perception

This slice adds a foreground, user-submit-only text surface to the consented
Android projection Activity. It closes one bounded direction:

`phone holder submits text -> authenticated ABT1 envelope -> ephemeral host observation`

It does not treat `mobile_input_text` as perception and does not add continuous
capture, dialogue injection, durable memory, attention authority, or actuation.

## Observation boundary

The `agent_bridge.mobile_text_observation.v0` payload binds the projection
session, capture time, locale, text SHA-256, `ephemeral_session_only` retention,
foreground user-submit evidence, and three authority fields fixed to false.
The host checks freshness, HMAC, digest, size, session binding, and a one-time
nonce before returning a signed acknowledgement. Rejected submissions remain
visible on the device rather than being cleared.

`mobile_projection_status` exposes the latest accepted observation only inside
the current MCP process. It neither promotes the text to memory nor interprets
it as an instruction. Any later semantic interpretation is a proposal, and any
real action remains subject to a separate authority decision.

## Verification scope

- pure Java protocol tests cover request and acknowledgement authentication and
  bounded text;
- Rust tests cover authenticated ingestion, zero authority, digest validation,
  and the existing projection lifecycle;
- the Android API 35 build produces an unsigned, aligned APK only inside the
  worktree build directory;
- no APK is installed and no real phone submission is claimed by this slice.

Voice input remains GSL-1D and requires separate push-to-talk, capture-consent,
VAD/ASR, raw-audio retention, and interruption semantics.
