# macOS Qwen3-TTS pilot

This is a **default-off** Qwen3-TTS CustomVoice pilot for the `present_voice`
embodiment lane. It does not change the default `tone` backend, and it never
silently substitutes macOS `say` when Qwen is unavailable.

## Runtime boundary

Keep PyTorch and `qwen-tts` in an isolated Python 3.12 environment. The
persistent worker uses this user-local runtime (outside the repository):

```sh
export AB_QWEN3_TTS_PYTHON="$HOME/.local/share/agent-bridge/qwen3-tts-venv/bin/python"
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

The former `/private/tmp/ab-qwen3tts-pilot` path is suitable only for one-shot
experiments: temporary storage can be cleared by the OS. The installer defaults
to the user-local runtime above. It can still be overridden with
`AB_QWEN3_TTS_PYTHON` for an explicitly managed runtime.

The adapter uses MPS with `float16` when available and intentionally does not
request FlashAttention: Qwen documents it as a CUDA optimization, not a macOS/MPS
requirement. A missing or unusable MPS runtime is an explicit synthesis failure;
there is no hidden CPU or `say` fallback.

## Optional persistent worker

The one-shot adapter remains the default diagnostic path. To remove repeated
model-load latency, start the **explicit, local-only** worker in the isolated
environment (it holds roughly 5–7 GB of unified memory while ready):

```sh
mkdir -p /Users/pallasting/.cache/agent-bridge/qwen3
"$HOME/.local/share/agent-bridge/qwen3-tts-venv/bin/python" scripts/qwen3_tts_worker.py \
  --socket /Users/pallasting/.cache/agent-bridge/qwen3/worker.sock \
  --model "$AB_QWEN3_TTS_MODEL" --device mps
```

The socket is owner-only and accepts one request at a time. It has no HTTP
listener and never plays audio. Opt in per MCP call with `qwen_worker`, or set
`AB_QWEN3_TTS_WORKER_SOCKET`; when a worker is selected, an unavailable worker
returns an explicit Qwen failure and does **not** fall back to one-shot Python or
macOS `say`.

### Worker contract and lower-resource nodes

The local socket is a versioned adapter boundary, not a promise that Qwen itself
has an ONNX build. A worker replies with `protocol: "ab.tts.worker.v1"`, its
actual `engine`, model, device, precision, and capabilities. The present local
implementation identifies itself as `qwen3-pytorch`, `float16`, and supports
`custom_voice`, `instruct`, and `zh`.

Any future resource-constrained node may provide a separately validated ONNX
worker only if it implements the same newline-delimited JSON contract:

```json
{"op":"health"}
{"op":"synthesize","text":"...","output":"/absolute/output.wav","speaker":"...","instruct":"..."}
```

It must accurately report its own engine (for example `onnxruntime`), model and
precision, and return an explicit error for unsupported features. Do not label a
different voice model as Qwen, silently discard `instruct`, or fall back to a
different engine. The existing `onnx-embed` feature and `RemoteEmbedBackend` are
embedding-only; they are not a TTS backend. This v1 transport is intentionally
Unix-socket local-only. Cross-node access requires a separate authenticated,
authorized transport and is not enabled by setting this environment variable.

## Pure-Rust pilot backend

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
an already-running MCP consumer must reconnect after deployed configuration
changes.

## Explicit MCP shape

Use the `qwen3` backend only after the isolated environment and model probe pass:

```json
{
  "backend": "qwen3",
  "text": "语音闭环已经准备完成。",
  "voice": "Serena",
  "qwen_instruct": "用平静、温暖、清晰的普通话播报，语速自然。",
  "qwen_python": "/Users/pallasting/Library/Application Support/agent-bridge/qwen3-tts-venv/bin/python",
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
