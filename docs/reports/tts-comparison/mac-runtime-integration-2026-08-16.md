# OmniVoice Mac runtime integration — 2026-08-16

## Decision

The Mac remote execution path is technically ready for the existing bounded
OmniVoice canary. It remains default-off. This validation does not authorize a
production-default change, a canary-percentage increase, or removal of Qwen3.

## Validated composition

- Runtime: Python 3.12, ONNX Runtime 1.28.0 on arm64 macOS
- Graphs: FP16 embeddings, FP32 bidirectional LLM and heads, FP16 decoder
- Decode steps: 32
- Output: mono PCM WAV at 24 kHz
- Component SHA-256 and byte sizes: verified from the node-local composition
  manifest before every synthesis

The node-local manifest contains machine paths and is deliberately not checked
into the repository.

## Results

| Gate | Result |
| --- | --- |
| Focused Python regression suite | 86 passed |
| Direct Mac adapter synthesis | passed; RTF 2.66 |
| SSH worker, WAV copy, and cleanup | passed; RTF 2.70 |
| `audio_embody.synth_omnivoice` entry | passed; RTF 2.58 |
| Checked-in 10% canary success route | bucket 747; assigned/executed `omnivoice` |
| Missing-manifest fault injection | assigned `omnivoice`; executed `qwen3`; fallback true |
| Qwen3 fallback WAV | passed; 1.7B CustomVoice, Serena, CPU float32, 24 kHz |

The successful cross-node artifact was 2.36 seconds, 113,324 bytes, with
SHA-256 `9ddf689f531f35921d53a12b9c465ebfb64b918a74aaa9dd8fdddcc29ba451bc`.
The UUID-scoped remote job directory was absent after the response was copied.

## Failure and authority boundaries

- Remote execution requires both the existing OmniVoice enable switch and the
  separate Mac-remote enable switch.
- The caller admits one remote decode at a time with a non-blocking lock.
- Text is carried in JSON over SSH stdin and is not interpolated into the SSH
  command.
- Worker output paths and cleanup IDs are structurally validated.
- Lock, timeout, SSH, manifest, inference, or copy failures return a candidate
  error to the existing canary router.
- The checked-in policy remains 10%, owner-allowlisted, and Qwen3 remains its
  control and candidate-error fallback.

## Environment repairs made during validation

- Mac OmniVoice venv: added `scipy` and `tokenizers` required by the checked-in
  bundle synthesizer.
- Local Qwen3 CPU venv: added `accelerate` required by its `device_map=cpu`
  load path.

These are isolated virtual-environment changes; no system Python or production
service configuration was modified.
