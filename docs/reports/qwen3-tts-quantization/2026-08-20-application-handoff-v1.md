# TTS quantization application handoff v1

Status: `QWEN_PRODUCTION_DEFAULT_OMNIVOICE_PILOT_ONLY`.

This handoff records the operational meaning of the completed quantization and
runtime evaluations. It does not authorize a checkpoint rewrite, quantized
runtime wiring, deployment, or backend promotion.

## Current application boundary

`config/tts-backend-capabilities.json` remains authoritative:

- `qwen3_custom_voice.production_default` is `true`. Qwen3-TTS remains the
  production backend for named speakers and instruction-controlled delivery.
- `omnivoice_onnx_candidate.production_default` is `false`. OmniVoice remains
  an explicitly enabled pilot candidate, with no named-speaker or style-
  instruction equivalence claim.
- The OmniVoice canary policy remains allowlisted and fallback-controlled; it is
  not a production-default switch.

## Evidence interpretation

The self-contained Qwen codec scope-3 audit pack records waveform and blinded
listening `PASS` on 4/4 cases, but runtime `FAIL` with only 2/4 runtime cases,
latency regression, and increased memory. The candidate therefore remains
rejected for runtime promotion.

The runtime-route decision separately rejects the reversible sidecar, current
packed MPS kernel, and current Core ML handoff. A three-module checkpoint rewrite
is deferred because the theoretical net model-memory saving is only 0.301%.

The OmniVoice static INT8 and autoregressive trajectory evidence also remain
rejected. A smaller artifact or a perceptually acceptable isolated sample is not
enough to replace the current backend.

## Safe operating procedure

For a new TTS candidate, use
`scripts/eval/tts_quantization_candidate_workflow.py` to create a self-contained
audit pack, then inspect `candidate.receipt.json`. Treat `reject` and
`insufficient_evidence` as non-promotion outcomes. Do not edit production
backend configuration in response to a numeric or listening `PASS` alone.

Reopening a quantized runtime requires a native fused kernel (or equivalent
without retained FP16 weights), at least 5% projected model-memory saving, full
frozen-corpus runtime coverage, end-to-end latency no worse than 1.05x, negative runtime-memory delta,
and fresh waveform plus blinded-listening evidence.
