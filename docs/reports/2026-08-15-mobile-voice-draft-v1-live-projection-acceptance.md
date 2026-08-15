# Mobile voice-draft V1 live projection acceptance

Date: 2026-08-15

## Verdict

`PASS_LIVE_PROJECTION_WITH_DUPLICATE_SUBMISSION_FINDING`.

The installed V1 Companion completed a real authenticated projection against a
short-lived LAN host. The phone rendered the expected frame and the host
accepted an ephemeral text observation. The run also exposed that an identical
submission can be accepted more than once.

## Live evidence

- device: `192.168.1.3:46035`, OPPO PKW110, Android 16;
- host: `192.168.1.2:17322`;
- session: `v1-live-20260815-d`;
- TTL: 600 seconds;
- rendered title: `Agent-Bridge V1`;
- rendered body: `Signed V1 projection acceptance.`;
- rendered state: `Read-only · revision 1 · disconnect anytime`;
- host logged repeated authenticated `served read-only frame` events from
  `192.168.1.3`;
- the foreground UI exposed the editable text draft, `DICTATE DRAFT`,
  `SUBMIT TEXT`, and `DISCONNECT` controls;
- no microphone permission was granted to Agent-Bridge and no audio was sent to
  the host;
- one two-character ephemeral draft digest was observed as
  `6aa8f49cc992dfd75a114269ed26de0ad6d4e7d7a70d9c8afb3d7a57a88a73ed`;
- the host logged two acceptance events for that same digest and character
  count.

## Product finding

`DUPLICATE_TEXT_SUBMISSION_NOT_DEDUPED`.

The live host accepted the same session-local text digest twice. This does not
expand retention or authority, but it means UI double taps or request retries
can produce duplicate observations. The next implementation gate should bind a
client-generated submission id or an equivalent session-local idempotency key
and reject/replay duplicate submissions without creating a second observation.

## Cleanup

The Companion process was force-stopped after evidence capture because the UI
did not visibly leave the content panel after the attempted disconnect input.
The projection host was then terminated before TTL expiry. Final device state:
launcher focused, no Companion PID, and no Companion service.
