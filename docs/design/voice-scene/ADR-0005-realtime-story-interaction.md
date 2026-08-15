# ADR-0005: S4 realtime interaction is dual-owner-gated

- Status: accepted for S4 implementation
- Date: 2026-07-29
- Ready state: `story_realtime_interaction_owner_gated_ready`
- Full exit state: `story_realtime_interaction_owner_gated` after an explicitly
  authorized microphone and audible-response trial

## Turn state machine

One bounded push-to-talk turn follows:

```text
story playing
  -> pause at exact position
  -> owner-authorized capture
  -> ASR
  -> character route
  -> S3 knowledge retrieval
  -> spoiler falsifier
  -> response TTS
  -> separately owner-authorized output
  -> resume exact position
```

Capture authorization and response-output authorization are separate. A caller
cannot infer microphone permission from output permission or vice versa.
Open-microphone/VAD mode is not enabled in S4; push-to-talk is the only capture
mode.

Every failure after pause returns to the exact stored playback position.
Capture, ASR, TTS, and output are sequential, so story playback and response
audio do not intentionally overlap.

## Grounding and branches

The transcript routes to an explicit named character when available, otherwise
to the session default. The routed question passes through S3's cursor and
`known_by` boundary. Any generated candidate then passes the spoiler falsifier
before TTS.

Each interaction creates only a proposal on a dedicated interaction branch.
It declares `writes_canon=false` and
`proposal_only_owner_review_required`.

## Retention and withdrawal

S4 supports:

- `none`: capture is deleted and transcript text is removed at turn end;
- `session`: artifacts remain in the caller's session scope;
- `durable_with_owner_review`: persistence may be proposed but requires owner
  review.

No turn silently promotes microphone audio, transcript, or simulation into
durable global memory.

## Truth boundary

Fixture adapters test orchestration without opening a microphone or sound
device. Full S4 exit requires a separately authorized real capture, ASR,
grounded response, TTS and audible delivery trial. Machine receipts alone do
not establish that human gate.
