# S5U existing ONNX text-to-WAV trial

S5U proves that the already downloaded CPU INT4 ONNX snapshot can turn local
Chinese text into a non-silent WAV without loading the original PyTorch model
or rebuilding any ONNX graph.

## Runtime

The isolated runtime is:

`/Data/Models/agent-bridge/tooling/qwen3-tts-onnx-runtime-py314`

It occupies 302,760,495 bytes. The direct fixed inputs are Python 3.14.4,
ONNX Runtime 1.28.0, NumPy 2.5.1, Transformers 4.57.3, and SoundFile 0.13.1.
All installed artifacts were binary wheels; no source build or Torch
installation occurred. Librosa was omitted because CustomVoice generation
does not resample reference audio.

## Bounded trial

The trial used:

- text: `你好，这是现有ONNX模型的最小合成测试。`
- speaker: `Vivian`
- language: `Chinese`
- generation: greedy, seed 0, maximum 8 codec frames
- provider: CPU only
- network during inference: disabled through local/offline Hugging Face mode

The durable WAV is stored outside the repository at:

`/Data/Models/agent-bridge/evidence/voice-scene/s5u-existing-onnx-20260730/trial.wav`

It is mono PCM16 at 24 kHz, 0.64 seconds, non-silent, and SHA-256 bound in the
S5U receipt. It was not played.

## Retained warning

Transformers reported that this tokenizer should be loaded with
`fix_mistral_regex=True`. The trial still generated a structurally valid WAV,
but S5U does not interpret that as linguistic correctness or naturalness.
Before a longer listening candidate, a trusted hash-bound runner should set
that option explicitly rather than modifying the downloaded community
snapshot.

S5U makes no human-audibility, naturalness, MI50, publisher-lineage, or
production-admission claim.
