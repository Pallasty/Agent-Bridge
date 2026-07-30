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

## S5G ModelScope snapshot evidence

The owner separately authorized and acquired
`onnx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice` from ModelScope. This is a
different 1.7B CustomVoice conversion and does not supersede the S5E/S5F 0.6B
streaming candidate. ModelScope exposed only the mutable `master` revision.

`story_voice_snapshot_audit.py` examined the complete local snapshot without
importing community Python, creating an ONNX Runtime session, loading external
tensor data, or using a GPU. The hash-bound receipt records:

- 71 files and exactly 36,202,013,026 bytes with no symlinks or incomplete
  files;
- six CPU/CUDA FP16, FP32, and INT4 variants with all manifest references
  present;
- SHA-256 for every file;
- 43 parsed ONNX graphs, ONNX opset 20, Microsoft domain opset 1, 45 distinct
  operator kinds, and five safe existing external-data locations;
- two Microsoft contrib operators: `MatMulNBits` and
  `GatherBlockQuantized`;
- an Apache-2.0 model-card declaration but no standalone license file; and
- a statically observed `subprocess.run` in the model-building utility
  `optimize.py`.

The static result is `blocked`. An immutable upstream revision, a standalone
license artifact or authoritative license resolution, and explicit review of
the build-time subprocess behavior are still required. The CUDA manifests name
`CUDAExecutionProvider`; they do not prove ROCm/MI50 compatibility. No
inference, parity, quality, audibility, or MI50 execution claim follows from
snapshot completeness.

## S5H CPU INT4 session-creation evidence

The owner authorized the next bounded goal after S5G:
CPU INT4 compatibility probing without graph execution or audio.
`story_voice_cpu_int4_smoke_gate.py` reads only the `cpu_int4/manifest.json`
references and launches one isolated child process per graph. Each child pins
`CPUExecutionProvider`, disables graph optimization, limits ONNX Runtime to one
intra-op and one inter-op thread, creates a session, records input/output
counts, and exits. It never calls `session.run()`.

Using isolated ONNX Runtime 1.28.0, all seven CPU INT4 graphs created sessions:
`code_predictor`, `codec_embed`, `residual_embed`, `talker_cache`,
`text_embed`, `tok_decoder`, and `tok_encoder`. The largest interface observed
was `talker_cache` with 59 inputs and 58 outputs. The receipt remains explicit
that no graph, token generation, waveform synthesis, GPU, community Python, or
audio output was exercised.

This promotes only the CPU INT4 lane to
`session_creation_passed_no_inference`. It does not clear S5G supply-chain
blockers, prove numerical correctness, prove that one autoregressive step can
run, establish real-time performance, or provide any MI50/ROCm evidence.

## S5I bounded CPU INT4 numeric evidence

The owner authorized the next bounded stage: one non-autoregressive,
non-audio graph execution. `story_voice_cpu_int4_numeric_probe.py` selects only
`cpu_int4/codec_embed.onnx`, validates its one-input/one-output contract, and
supplies the fixed synthetic input `codec_ids=int64[[0, 1, 2, 3]]`. It runs
the same input twice in an isolated CPU-only session and retains only shape,
dtype, finite-value statistics, and output hashes.

Under ONNX Runtime 1.28.0 both executions produced the same SHA-256. The
output was finite `float32[1,4,2048]`, with values bounded between
-0.07802734524011612 and 0.08056640625 for this fixture. No output was passed
to the talker, tokenizer, or decoder.

This promotes only `codec_embed` to
`numeric_probe_passed_no_audio`. It does not validate semantic codec IDs,
numerical parity against the source framework, other ONNX graphs,
autoregressive generation, waveform decoding, latency, voice quality,
audibility, supply-chain clearance, or MI50/ROCm execution.

## S5J bounded CPU INT4 code-predictor evidence

The next owner-authorized stage executes only
`cpu_int4/code_predictor.onnx`. The probe validates the two-input contract and
uses fixed zero fixtures: `talker_hidden=float32[1,2048]` and
`codec_ids=int64[1,16]`. It runs twice under the same isolated, CPU-only,
single-thread configuration and retains only output statistics and hashes.

Both executions produced the same SHA-256. The output was finite
`group_logits=float32[1,15,2048]`, with values between
-21.297151565551758 and 19.180789947509766 for the zero fixture. The probe did
not select an argmax, sample codec IDs, or feed any result into another graph.

This promotes only the isolated code-predictor graph to
`predictor_probe_passed_no_generation`. It does not validate that zero
fixtures are semantically meaningful hidden states, establish source-model
parity, implement an autoregressive loop, generate tokens, decode waveforms,
measure quality or latency, clear supply-chain blockers, or prove MI50/ROCm
support.

## S5K bounded CPU INT4 talker-cache evidence

The next owner-authorized stage executes one zero-history step of
`cpu_int4/talker_cache.onnx`. The probe supplies a deterministic synthetic
`float32[1,1,2048]` embedding linearly spanning `[-0.01, 0.01]`, zero position
IDs, an enabled one-token attention mask, and 56 empty
`float32[1,8,0,128]` key/value inputs. An earlier all-zero embedding produced
all-zero logits and was rejected as degenerate rather than promoted as useful
numeric evidence.

Under ONNX Runtime 1.28.0, both bounded executions produced the same aggregate
SHA-256,
`87b234ae0265c7e670b7e7c0b28165382304f3ae0af0f13cbb206605e31b2454`.
The output included finite, nonzero `float32[1,1,3072]` logits ranging from
-16.334016799926758 to 10.391515731811523, a finite
`float32[1,1,2048]` hidden state, and 56 finite present-cache tensors with
shape `float32[1,8,1,128]`.

This promotes only one synthetic zero-past talker step to
`talker_single_step_passed_no_sampling`. The produced cache was inspected but
never fed into a subsequent step. The probe performs no argmax or sampling,
autoregressive loop, token generation, waveform decoding, GPU work, or
community-Python import. It does not prove semantic prefill correctness,
source-model parity, sustained generation, voice quality, real-time
performance, supply-chain clearance, or MI50/ROCm support.
