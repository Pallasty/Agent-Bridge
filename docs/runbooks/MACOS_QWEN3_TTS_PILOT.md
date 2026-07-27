# macOS Qwen3-TTS pilot

This is a **default-off** Qwen3-TTS CustomVoice pilot for the `present_voice`
embodiment lane. It does not change the default `tone` backend, and it never
silently substitutes macOS `say` when Qwen is unavailable.

## Runtime boundary

Keep PyTorch and `qwen-tts` in an isolated Python 3.12 environment. The current
pilot environment is deliberately outside the repository:

```sh
export AB_QWEN3_TTS_PYTHON=/private/tmp/ab-qwen3tts-pilot/bin/python
export AB_QWEN3_TTS_MODEL=/Users/pallasting/.cache/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master
export AB_QWEN3_TTS_DEVICE=mps
```

`scripts/qwen3_tts_synth.py` runs in that environment; the Agent-Bridge Rust
process and system Python do not import PyTorch. The expression-control baseline
is the official CustomVoice 1.7B model and its `speech_tokenizer/` subtree. The
current macOS host has a complete ModelScope snapshot at the path above. Point
`AB_QWEN3_TTS_MODEL` at a complete local snapshot rather than relying on an
implicit first-request download. Do not add weights, virtual environments, or
generated WAV files to Git.

The adapter uses MPS with `float16` when available and intentionally does not
request FlashAttention: Qwen documents it as a CUDA optimization, not a macOS/MPS
requirement. A missing or unusable MPS runtime is an explicit synthesis failure;
there is no hidden CPU or `say` fallback.

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

## Evidence boundary

On macOS, `synth_file_stt` proves that Whisper can recover the requested words
from the generated WAV. It does not prove the output bus, speaker, headphone, or
human listener. Complete delivery still needs the existing serialized `afplay`
receipt plus `present_voice_confirm_audibility` for that specific artifact.

## Quantization decision

Use official FP16/MPS CustomVoice 1.7B as the quality baseline. ONNX, INT8, and
INT4 exports are separate community-runtime experiments; they must reproduce the
same Chinese expression corpus and physical-delivery acceptance before becoming an
available backend. Do not select INT4 merely to reduce memory on this host.
