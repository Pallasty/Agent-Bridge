# GSL-1 Grounded Surface Loop

Status: GSL-1A implementation. Mobile sensing phases are planned, not admitted.

## User value

Agent-Bridge should first help an agent understand the user's current working
state and express that understanding as an inspectable result. The practical
loop is:

`observe -> state card -> local render verification -> receipt`

GSL-1 does not claim continuous perception, autonomous action, human attention,
or a physical-device effect.

## GSL-1A: bounded local projection

`grounded_surface_present` is the only presentation tool added to
`codex-lean`. It wraps the existing `present` implementation with fixed policy:

- structured table payload only;
- 1-64 observation rows and at most 128 KiB encoded input;
- required source, status, observation timestamp, and freshness;
- local file sink, browser verification requested, interactivity disabled;
- no caller-provided HTML, SVG, Mermaid, JavaScript, channel, or verification
  override;
- provenance says what was requested and never claims that a human saw the
  artifact or that a device displayed it.

The first dogfood card should combine currently available sources such as
`body_status`, `project_detect`, `changes_digest`, `ide_snapshot`,
`mobile_list_devices`, and `mobile_projection_status`. A missing producer or
disconnected device is a typed `freshness=unavailable` observation, not an
empty success.

## Mobile phases

The owner can enable wireless ADB on demand. Device connection is therefore an
explicit test prerequisite, not a permanent runtime assumption.

### GSL-1B: consented mobile projection

After the owner connects the device:

1. identify the exact wireless ADB serial;
2. run read-only health and capability probes;
3. request the existing device-holder projection consent;
4. start one TTL-bounded session and project a GSL state card;
5. authenticate pull/readback and stop the session;
6. record what was delivered without claiming that the owner saw it.

No lifecycle write is exposed to the lean profile before this proof passes.

### GSL-1C: mobile text perception

Add an explicit companion text-input surface that produces a bounded
observation envelope containing source device, capture time, locale, payload
digest, retention policy, and user-submit consent. Text is never inferred from
ADB control commands, and `mobile_input_text` remains an actuator rather than a
perception source.

Admission requires authenticated origin, foreground/user-submit evidence,
freshness, replay protection, and a no-background-capture default.

### GSL-1D: mobile voice perception

Add push-to-talk only after text perception is useful. The first version keeps
raw audio ephemeral and returns transcript, language, timestamps, confidence,
audio digest, and explicit consent/retention fields. It must distinguish:

- microphone capture succeeded;
- speech decoding succeeded;
- semantic interpretation is only a proposal;
- any resulting action still needs its own authority decision.

Continuous listening, wake-word operation, background recording, speaker
identity, model fitting, and action execution are separate future gates.

## Promotion evidence

GSL-1A is useful only if at least ten real tasks produce provenance-complete
cards, at least 90% render successfully, no stale observation is accepted as
fresh, and no receipt overclaims a human or physical-device effect. Mobile
phases must additionally prove exact-device selection, consent, authenticated
readback, bounded lifetime, and teardown.
