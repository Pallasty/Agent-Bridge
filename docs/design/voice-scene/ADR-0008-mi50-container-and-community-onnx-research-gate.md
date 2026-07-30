# ADR-0008: MI50 container and community ONNX research gate

## Status

Accepted for S5D-Research on 2026-07-30.

## Context

The S5C blind audition did not promote the AISHELL-3 three-voice pack. The
owner identified an existing MI50 Docker lane and allowed an unverified
community Qwen ONNX export to be investigated.

The local host has both `renderD128` (WX 3200) and `renderD129` (MI50).
Existing AiOT assets pin ROCm 5.7 and `HSA_OVERRIDE_GFX_VERSION=9.0.6`, but
the Compose service uses `privileged: true` and does not limit the exposed
DRI node. That configuration is useful prior evidence, not a safe TTS trial
contract.

## Decision

1. Rust remains the orchestration, policy, receipt, caching, and streaming
   boundary. A model may execute in an isolated container or sidecar.
2. An MI50 TTS trial must expose only `/dev/kfd` and
   `/dev/dri/renderD129`, use a digest-pinned image, disable runtime network,
   use a read-only root filesystem, and avoid privileged mode.
3. A community ONNX export is blocked until its source revision, license,
   complete file hashes, operator inventory, text model, speech tokenizer,
   vocoder, and reference parity artifact are verified.
4. Passing the static gate means only `trial_plan_ready`. It never means
   production eligibility, model quality, GPU correctness, or audibility.
5. This unit does not download models, build or start containers, use the
   GPU, play audio, or enable an Agent-Bridge runtime backend.

## Candidate order

1. Qwen3-TTS 0.6B community streaming ONNX as the MI50 experiment.
2. Qwen3-TTS 0.6B pure-Rust/Candle as the Rust portability experiment.
3. Official Qwen3-TTS 0.6B CustomVoice as the quality reference.
4. Fun-CosyVoice 3 as the second quality reference.

The official reference and community conversions are separate evidence
lanes. A community conversion cannot inherit upstream correctness or license
claims without verification.

## S5E evidence

S5E adds `mi50_qwen_onnx.compose.yaml`, an inert profile based on the locally
observed ROCm 5.7 image digest. It is protected by a non-default Compose
profile and `/bin/false`; those controls make it a reviewable isolation
artifact, not an inference runtime.

The selected community repository has one pinned historical revision and a
model-card Apache-2.0 declaration. Direct API and Git HEAD resolution failed
from the local host, and the repository root did not expose a separately
verified license file. No weight was downloaded. Consequently
`qwen3_tts_streaming_onnx_supply_chain.json` remains
`metadata_pinned_weights_blocked`.

## S5F evidence

The owner authorized only fixed-revision source, configuration, and
license-related small files. `story_voice_small_file_audit.py` enforces a
path allowlist, rejects model/audio/log paths, applies per-file and total byte
limits, publishes atomically, and scans Python with `ast` without importing
it.

All available host transports to the fixed Hugging Face revision failed by
connection reset, HTTP 502, or bounded fetch failure. The final evidence
directory was not created and the empty temporary directory was removed.
Search-indexed `main` content was not substituted for the fixed revision.
Therefore the code audit remains blocked rather than inferred from partial or
mutable content.
