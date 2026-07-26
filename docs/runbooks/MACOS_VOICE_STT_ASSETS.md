# macOS voice STT assets

Agent-Bridge's macOS `present_voice` path uses native `/usr/bin/say` for speech
synthesis and OpenAI Whisper only to transcribe the synthesized WAV. This proves
that the file is intelligible; it does not prove that the output bus or physical
speaker emitted audible sound.

## Runtime and license

- Runtime: Homebrew `openai-whisper` (`/opt/homebrew/bin/whisper`)
- Upstream: <https://github.com/openai/whisper>
- License: MIT for the code and model weights
- Homebrew formula: `openai-whisper`

## Model cache

Whisper stores downloaded checkpoints outside the repository:

```text
~/.cache/whisper/
```

The minimal default for Agent-Bridge macOS voice verification is the multilingual
`tiny` model:

```text
~/.cache/whisper/tiny.pt
sha256 65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9
```

The hash is encoded in OpenAI Whisper's official model URL and is checked by
Whisper when it downloads or reuses the checkpoint.

Configure an explicit runtime when needed:

```sh
export AB_TTS_WHISPER_BIN=/opt/homebrew/bin/whisper
export AB_TTS_WHISPER_MODEL=tiny
```

Model checkpoints are cache assets, not source assets. Do not add them to Git.
Deleting `~/.cache/whisper/tiny.pt` is a recoverable cleanup: the Whisper loader
will download and hash-check it again on the next use.

## Acceptance boundary

A complete receipt has two separate pieces of evidence:

1. `verify_method=synth_file_stt` and `verify_status=rendered_ok` establish that
   Whisper recovered the requested words from the synthesized file.
2. `present_voice_confirm_audibility` records a human report for that one
   playback outcome.

Neither evidence may be generalized to a different file, output device, volume
state, or later run.
