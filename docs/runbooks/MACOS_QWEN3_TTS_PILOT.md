# macOS Qwen3-TTS pilot

This runbook covers the **default-off** Python and Rust Qwen3-TTS CustomVoice
pilots for the `present_voice` embodiment lane. Neither changes the default
`tone` backend, and neither silently substitutes macOS `say` when Qwen is
unavailable.

## Python runtime boundary

Keep PyTorch and `qwen-tts` in an isolated Python 3.12 environment. The current
pilot environment is deliberately outside the repository:

```sh
export AB_QWEN3_TTS_PYTHON=/private/tmp/ab-qwen3tts-pilot/bin/python
export AB_QWEN3_TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
export AB_QWEN3_TTS_DEVICE=mps
```

`scripts/qwen3_tts_synth.py` runs in that environment; the Agent-Bridge Rust
process and system Python do not import PyTorch. The first real request downloads
the official CustomVoice 0.6B model and the tokenizer into the normal model cache.
Do not add weights, virtual environments, or generated WAV files to Git.

The adapter uses MPS with `float16` when available and intentionally does not
request FlashAttention: Qwen documents it as a CUDA optimization, not a macOS/MPS
requirement. A missing or unusable MPS runtime is an explicit synthesis failure;
there is no hidden CPU or `say` fallback. CPU execution remains available only as
an explicit diagnostic override via `AB_QWEN3_TTS_DEVICE=cpu`; it is outside the
accepted macOS pilot path.

## Explicit MCP shape

Use the `qwen3` backend only after the isolated environment and model probe pass:

```json
{
  "backend": "qwen3",
  "text": "语音闭环已经准备完成。",
  "voice": "Serena",
  "qwen_instruct": "用平静、温暖、清晰的普通话播报，语速自然。",
  "qwen_python": "/private/tmp/ab-qwen3tts-pilot/bin/python",
  "capture_channel": "synth_file"
}
```

For Chinese CustomVoice, begin with Qwen's Chinese-native voices `Serena`,
`Vivian`, `Uncle_Fu`, `Dylan`, or `Eric`. `qwen_instruct` is recorded only as a
boolean (`qwen_instruct_applied`) in the adapter receipt; it avoids placing a
potentially sensitive instruction verbatim into a general status field.

## Rust runtime boundary

The pure-Rust adapter is a separate backend named `qwen3-rust`. It remains
unavailable unless all of the following are explicit in the MCP process:

```sh
export AB_QWEN3_TTS_RUST_ENABLED=1
export AB_QWEN3_TTS_RUST_BIN=/absolute/path/to/qwen-tts
export AB_QWEN3_TTS_RUST_MODEL_DIR=/absolute/path/to/Qwen3-TTS-12Hz-1.7B-CustomVoice
export AB_QWEN3_TTS_RUST_PROFILE=1.7b-customvoice
export AB_TTS_WHISPER_MODEL=base
```

Selecting `backend=qwen3-rust` is not sufficient by itself. The enable flag,
binary, model directory, and integrity profile are all required. The adapter
does not search `PATH`, download weights, infer a profile, or fall back to
Python or `say`.

The current 1.7B profile checks exact size and SHA-256 for both model objects
before every synthesis, then invokes the local arm64 CLI with fixed
`--device metal --dtype f16`. The 1.7B Rust speaker registry is lowercase; use
`serena`, not `Serena`.

The MCP shape is:

```json
{
  "backend": "qwen3-rust",
  "text": "你好，这是 Agent Bridge 的纯 Rust 语音试验。",
  "voice": "serena",
  "capture_channel": "synth_file",
  "qwen_rust_bin": "/absolute/path/to/qwen-tts",
  "qwen_rust_model_dir": "/absolute/path/to/Qwen3-TTS-12Hz-1.7B-CustomVoice",
  "qwen_rust_profile": "1.7b-customvoice",
  "stt_model": "base"
}
```

`present_voice` is a Niche tool, so the source must be built/exposed with the
`all` tool profile for direct MCP use. Environment changes are process-scoped;
an already-running MCP consumer must reconnect after the deployed process
configuration changes.

## Evidence boundary

On macOS, `synth_file_stt` proves that Whisper can recover the requested words
from the generated WAV. It does not prove the output bus, speaker, headphone, or
human listener. Complete delivery still needs the existing serialized `afplay`
receipt plus `present_voice_confirm_audibility` for that specific artifact.

The accepted Rust fixture reached word overlap `0.846` with Whisper `base`.
Another legitimate sentence reached only `0.786` and was correctly returned as
`no_capture`. Do not lower the `0.8` threshold merely to turn variable
utterances green; a human hearing pleasant audio is complementary evidence,
not a replacement for the file-level falsifier.

## Quantization decision

Use official FP16 CustomVoice weights on the native Apple accelerator as the
quality baseline: MPS for the Python pilot and Metal for the Rust pilot. ONNX, INT8, and
INT4 exports are separate community-runtime experiments; they must reproduce the
same Chinese expression corpus and physical-delivery acceptance before becoming an
available backend. Do not select INT4 merely to reduce memory on this host.
