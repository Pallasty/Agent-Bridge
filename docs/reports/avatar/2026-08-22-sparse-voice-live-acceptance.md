# Sparse Avatar voice live acceptance — 2026-08-22

## Decision

Freeze the current owner-local sparse voice configuration as the accepted
baseline for practical use. Do not change loudness or expression parameters as
part of this acceptance closure.

## Accepted configuration

- renderer: native transparent Linux Face, independently supervised;
- observer: `avatar voice-observe`, read-only pet-sidecar polling;
- synthesis: authenticated SSH dispatch to the Mac Qwen3-TTS CustomVoice
  worker (`qwen3-pytorch`, MPS, FP16);
- voice profile: `cute_playful` v1, Serena;
- playback gain: `+8 dB`, applied only to an ephemeral playback copy;
- peak protection: FFmpeg limiter at `0.944`, with automatic output leveling
  disabled;
- sink, music stream and system master volume: unchanged;
- poll interval: 500 ms;
- cooldown: 300 seconds;
- successful utterance budget: three per bounded observer segment;
- allowed lines: fixed lifecycle templates only;
- `verified` speech: requires a structured verification outcome identifier.

## Verified evidence

The deployed source was Agent-Bridge master commit `8c430f6a`. Deployment
passed the build-from-master currentness check, binary capability superset gate,
and audio-adapter parity check. After Codex restart, `agent-bridge doctor`
reported no non-OK checks.

The live supervisor reported a running renderer, a stable voice supervisor, a
live voice observer, and a reachable renderer-state endpoint. The Mac worker
health probe returned protocol `ab.tts.worker.v1`, state `ready`, engine
`qwen3-pytorch`, device `mps`, and capabilities `custom_voice`, `instruct`, and
`zh`.

A real pet-sidecar transition from `working` to `verified` used outcome id
`verification:avatar-sparse-voice-gain/20260822:live-plus8db`. Auto ritual was
disabled, so the persistent observer was the only authorized playback path.
The fixed line was “验证已经通过。”.

## Owner listening verdict

Accepted: clear, sufficiently loud, with no audible clipping or compression.
The owner noted that speech was slightly fast. This is a non-blocking preference
for a future voice-profile trial, not a reason to alter the accepted baseline.

## Boundaries and rollback

This acceptance proves the operator-heard result for this playback and the
observed runtime configuration. It does not establish universal loudness across
other sinks or background-music levels. Sparse voice remains opt-in and does
not write pet state, write presence, start a renderer, control desktop input,
or listen continuously.

Rollback loudness without changing system volume by launching with
`AB_FACE_VOICE_GAIN_DB=0`. Fully disable the observer with
`AB_FACE_VOICE_ENABLED=0` and restart the session-owned launcher.

