# ADR-0003: S2 offline rendering is provenance-bound and owner-gated

- Status: accepted for S2 implementation
- Date: 2026-07-29
- Machine exit state: `story_offline_render_verified_player_ready`
- Full S2 exit state: `story_offline_playback_verified` only after owner playback
  and human audition evidence

## Render contract

`story_offline_render.py` consumes a reviewable S1 plan plus an explicit backend
profile. A backend profile binds backend/model identity, exact model and binary
SHA-256, and a capability matrix. The renderer receipt must agree on backend,
model, voice, and output path. A zero exit or RIFF-like header alone is not
success.

Every cache key binds:

- source fingerprint and version;
- exact segment text;
- model fingerprint;
- voice-profile ID and version;
- speed, gain, and pause controls.

Source, model, profile, or render-control drift therefore invalidates only the
affected segment. Failed segments retry independently within a bounded limit.

## Verification and assembly

Each segment must be a decodable mono PCM16 WAV with meaningful duration and
non-zero RMS. Assembly preserves event order, normalizes each segment to a
bounded PCM target, inserts configured pauses, and emits a chapter manifest
with segment and chapter hashes. Missing, reordered, silent, malformed, or
hash-mismatched artifacts fail closed.

The current assembler supports speed through the backend, PCM gain/
normalization, and pauses. Pitch is explicitly unsupported rather than silently
ignored.

## Player boundary

Player state supports start, pause, resume, status, and rewind checkpoints.
Start and resume require `owner_authorized=true`. Tests exercise the state
machine with `emit_audio=false`; they never activate a sound device.

Machine WAV verification does not prove intelligibility, character quality,
physical playback, or audibility. The final S2 roadmap state remains gated on
an explicit owner playback command and a human audition linked to the exact
chapter artifact hash.

## Current backend evidence

The Linux host has an installed `ab-tts-synth` binary and local Kokoro v1.0
model/voice assets. S2 uses it only as an offline English render lane. Chinese
multi-speaker quality and audition remain S5 work; no model was downloaded for
this stage.
