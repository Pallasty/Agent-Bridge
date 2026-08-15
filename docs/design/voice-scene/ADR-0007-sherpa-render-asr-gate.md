# ADR-0007: S5B publishes three-voice packs atomically

- Status: accepted for S5B implementation
- Date: 2026-07-29
- Exit state for this unit: `chinese_three_voice_pack_machine_verified`
- Full S5 exit remains: `story_chinese_multispeaker_verified`

## Decision

S5B uses the existing opt-in Rust Sherpa VITS backend through a separate,
integrity-gated render process. It verifies every official AISHELL-3 asset
before starting inference and writes three candidates into a temporary sibling
directory. The final output directory appears only after all renders and WAV
checks succeed. Existing output directories are never overwritten.

Every candidate binds the audition plan, opaque speaker ID, profile version,
reference text, synthesis receipt, PCM shape, and SHA-256. No character voice
mapping is promoted by machine evaluation.

## Chinese intelligibility

The first multilingual Whisper tiny probe correctly failed the initial
homophone-heavy sentence, with CER from 0.70 to 0.90. The result was preserved
as a negative control; the threshold was not weakened.

The final benchmark uses the neutral fixed sentence:

`今天阳光很好，我们一起回家。`

The official Sherpa SenseVoice int8 model is a second, Chinese-oriented ASR
probe. Its binary, model, tokens, and packaged license pointer are all
hash-bound. The final speaker 10/33/99 pack produced exact transcripts for all
three files and therefore CER 0.0. This proves file-level machine
intelligibility for one fixed sentence only.

## Isolation and promotion

The TTS model, Rust synthesis binary, Sherpa ASR runtime, Whisper model, and
SenseVoice model live under `/Data/Models/agent-bridge/sherpa-onnx`. They are
not installed in system PATH, not enabled in Agent-Bridge, and not selected by
default. Playback remains a separate owner-authorized S5C action.

AISHELL-3 model-weight licensing remains unverified because its release archive
contains no license file. SenseVoice includes a license pointer, but that does
not alter the AISHELL-3 restriction. No model or generated audio is committed
to Git.

## Non-claims

S5B does not prove blind human distinguishability, naturalness, role fit,
long-form consistency, expressive instruction following, or production
licensing. It does not play audio, bind gender, clone a real voice, write canon,
deploy a service, or enable a runtime backend.
