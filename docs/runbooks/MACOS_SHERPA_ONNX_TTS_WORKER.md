# macOS Sherpa-ONNX TTS worker

This is the low-resource, CPU-only TTS fallback for Agent-Bridge nodes that
cannot keep Qwen3-TTS resident. It is explicit and default-off: installing the
worker does not replace Qwen, change the default backend, open a network port,
or silently accept unsupported expression instructions.

## Supported model and evidence boundary

The initial asset is the official `vits-icefall-zh-aishell3` package. It is a
Chinese-only, 174-speaker VITS model whose output is 8 kHz. Its lexicon drops
out-of-vocabulary English words instead of spelling them, so mixed Chinese and
English input is outside this fallback's contract. Speaker IDs are not treated
as names, genders, or quality guarantees; only explicitly auditioned IDs are
exposed through `AB_TTS_SHERPA_VOICE_MAP`.

Official archive:

```text
https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-icefall-zh-aishell3.tar.bz2
```

Current audited archive SHA-256:

```text
ab468db3a3308cdd861495e0db2f25d79418a0c00639f74944c7cdf5dd8c6ec1
```

The runtime reports `dtype=unknown` unless an audited asset manifest establishes
the graph precision. Do not relabel it FP32, INT8, or INT4 based only on the
`.onnx` suffix.

## Model installation

Keep weights outside Git:

```sh
mkdir -p "$HOME/.cache/agent-bridge/tts-models"
curl -fL \
  -o "$HOME/.cache/agent-bridge/tts-models/vits-icefall-zh-aishell3.tar.bz2" \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-icefall-zh-aishell3.tar.bz2
shasum -a 256 "$HOME/.cache/agent-bridge/tts-models/vits-icefall-zh-aishell3.tar.bz2"
tar -xjf "$HOME/.cache/agent-bridge/tts-models/vits-icefall-zh-aishell3.tar.bz2" \
  -C "$HOME/.cache/agent-bridge/tts-models"
```

Required runtime assets are `model.onnx`, `lexicon.txt`, `tokens.txt`,
`phone.fst`, `date.fst`, and `number.fst`.

## Install the persistent worker

The installer builds the opt-in Rust/Sherpa binary in release mode, copies it
under `~/.local/lib/agent-bridge`, and starts an owner-local LaunchAgent:

```sh
AB_TTS_SHERPA_MODEL_DIR="$HOME/.cache/agent-bridge/tts-models/vits-icefall-zh-aishell3" \
AB_TTS_SHERPA_VOICE_MAP="speaker_66=66,speaker_21=21,speaker_45=45" \
scripts/install-sherpa-tts-worker-macos.sh
```

The socket directory is mode `0700` and the Worker v1 socket is mode `0600`.
Requests are serialized. The worker has no HTTP listener and never plays audio.

## Validate and explicitly use it

Health and real synthesis:

```sh
python3 scripts/validate_tts_worker_contract.py \
  --socket "$HOME/.cache/agent-bridge/sherpa/worker.sock" \
  --expected-engine sherpa-onnx \
  --require-capability zh \
  --require-capability multi_speaker \
  --text "低资源节点语音服务已经准备完成。" \
  --output /private/tmp/ab-sherpa-smoke.wav \
  --speaker speaker_66
```

Agent-Bridge invocation:

```sh
python3 scripts/audio_embody.py --json --mode speech \
  --capture-channel synth_file --synth-backend sherpa \
  --sherpa-worker "$HOME/.cache/agent-bridge/sherpa/worker.sock" \
  --voice speaker_66 --text "低资源节点语音服务已经准备完成。"
```

The worker advertises only `zh`, `multi_speaker`, and `speed`. A non-empty
`instruct` is rejected; it is never silently discarded. A healthy socket and a
written WAV do not prove intelligibility or physical-speaker delivery. Promotion
requires synthesized-file STT plus a human confirmation of the exact played
artifact. The current 8 kHz model is a compatibility and availability fallback,
not a quality-equivalent replacement for Qwen3-TTS. On the initial macOS probe,
all three exposed speaker IDs missed the automated STT threshold (best overlap
about 0.52), so the worker remains available only by explicit selection and is
not admitted as an automatic failover.

## Rollback

```sh
launchctl bootout "gui/$(id -u)/com.pallasting.agent-bridge.sherpa-tts"
```

This stops the fallback worker without touching the Qwen worker or Agent-Bridge.
