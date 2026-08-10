# Qwen3-TTS entropy-guided quantization v0

Date: 2026-07-27  
Status: `Q2_ONE_SHOT_FUNCTIONAL_SENSITIVITY_BLOCKED_CONTROL_LOGIT_REPLAY`  
Evidence:
[`2026-07-27-entropy-preflight.md`](../reports/qwen3-tts-quantization/2026-07-27-entropy-preflight.md)

Q0/Q1 result:
[`2026-07-27-q0-q1-result.md`](../reports/qwen3-tts-quantization/2026-07-27-q0-q1-result.md)

Q2 FP16 baseline:
[`2026-07-27-q2-fp16-baseline.md`](../reports/qwen3-tts-quantization/2026-07-27-q2-fp16-baseline.md)

Q2 thresholds and activation plan:
[`2026-07-27-q2-thresholds-and-activation-plan.md`](../reports/qwen3-tts-quantization/2026-07-27-q2-thresholds-and-activation-plan.md)

Q2 activation calibration:
[`2026-07-27-q2-activation-calibration.md`](../reports/qwen3-tts-quantization/2026-07-27-q2-activation-calibration.md)

Q2 one-shot functional sensitivity:
[`2026-07-27-q2-functional-sensitivity-one-shot.md`](../reports/qwen3-tts-quantization/2026-07-27-q2-functional-sensitivity-one-shot.md)

Q2 baseline capture and paired reference evidence are complete for the frozen
16-case corpus. The accepted Worker v1 produced three complete 16/16 runs on
MPS/float16. Whisper, emotion2vec, and CAM++ receipts are frozen as paired
candidate references, without claiming that automated metrics replace human
listening.

The threshold contract, blinded protocol, and v1 activation policy are frozen.
The v1 plan selects 96 of 196 eligible talker attention/MLP modules across all
28 layers. A separate MPS/float16 process completed all 96 × 16 observations
with exact parameter binding, 4,096 finite samples per observation, zero empty
activations, and zero sampled nonfinite values. The independent activation gate
returned `READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN`. Fake quantization,
quantized-weight writing, candidate generation, runtime wiring, fallback, and
promotion all remained unauthorized at that gate.

A later, separately frozen one-shot gate admitted exactly one non-writing
fake-Q8 forward-proxy measurement. It restored all model/runtime state and
left the accepted Worker untouched. Control speech codes replayed exactly, but
raw talker and predictor-head-0 logits did not replay byte-for-byte. The trial
therefore returned
`BLOCKED_CONTROL_NONDETERMINISM_OR_RESTORATION_UNPROVEN`; restoration itself
was proven, but functional attribution was not. The authorization is consumed,
no quantized candidate exists, and Q3 remains closed.

## 1. Purpose

Design a model-aware quantization tool for the same-family
`Qwen3-TTS-12Hz-1.7B-CustomVoice` checkpoint while preserving Agent-Bridge's
accepted FP16/MPS voice lane as the authoritative quality baseline.

The tool is named `ab-qwen-quant` in this design. It is an offline research
tool, not a voice backend. It does not play audio, start a worker, download
assets, or alter the currently selected TTS route.

## 2. Authority boundary

Voice is a non-authoritative projection of canonical semantic intent:

```text
canonical intent
  -> versioned voice projection request
  -> TTS renderer
  -> immutable audio artifact and engine receipt
  -> delivery and exact-artifact human confirmation
```

Quantization may change the renderer implementation. It cannot change the
canonical text, silently discard speaker or instruction fields, relabel a
different model as Qwen, or inherit the FP16 worker's acceptance.

## 3. Non-goals

V0 does not:

- quantize weights during a live request;
- dynamically repack a resident model;
- claim ONNX or GGUF support without a pinned runtime writer and consumer;
- quantize the codec merely because a tensor has high entropy;
- implement INT4 or INT2 before Q8/INT8 quality evidence;
- modify the Worker v1 contract;
- introduce an automatic fallback;
- sync, deploy, or replace the current worker.

“Dynamic” in v0 means offline, evidence-guided mixed-precision planning.
Runtime profile selection between separately built and admitted artifacts is a
future design.

## 4. Extracted engineering patterns

The useful ArrowQuant V2 patterns become format-neutral interfaces:

```text
TensorSource
  -> DiagnosticSuite
  -> PrecisionPlanner
  -> Quantizer
  -> BitPacker
  -> RuntimeWriter
  -> CandidateValidator
```

### 4.1 TensorSource

Responsibilities:

- read SafeTensors headers without materializing the model;
- preserve exact tensor names, shapes, dtype, offsets, source file, and source
  hashes;
- stream one tensor or bounded group at a time;
- distinguish `talker`, `code_predictor`, and `speech_tokenizer_codec`;
- refuse unsupported or ambiguous dtypes.

### 4.2 DiagnosticSuite

Static diagnostics per tensor:

- normalized Shannon entropy at 64, 256, and 1024 bins;
- entropy percentile within the same module and tensor family;
- robust entropy after percentile clipping;
- absmax, RMS, variance, kurtosis, zero ratio, and outlier ratios;
- Q8 and Q4 simulated reconstruction error;
- group-wise error candidates for several group sizes;
- estimated packed bytes including scales, zero points, alignment, and runtime
  metadata.

Calibration diagnostics:

- activation range, entropy, kurtosis, and outliers over a frozen corpus;
- request strata: short/long Chinese, numbers, punctuation, mixed Chinese and
  English, speaker, expression instruction, and deterministic seed where the
  runtime supports it;
- exact model, runtime, corpus, prompt, and hook version hashes.

Functional diagnostics where the runtime exposes the required boundary:

- FP16 versus candidate speech-token agreement;
- per-step logit KL/JS divergence and top-k retention;
- EOS timing and generated-token length drift;
- code-predictor stream divergence;
- codec-latent similarity and spectral/prosodic diagnostics;
- synthesized-file STT, speaker consistency, instruction adherence, and
  exact-artifact human playback.

Entropy is one feature in this suite. It is never a promotion gate by itself.

### 4.3 PrecisionPlanner

The planner operates under an explicit packed-size or resident-memory budget.
It cannot use fixed universal entropy thresholds.

Each tensor receives:

```text
TensorDecision {
  logical_name
  partition
  tensor_family
  source_dtype
  candidate_dtype
  group_size
  packing
  static_diagnostics
  activation_diagnostics
  functional_sensitivity
  decision_reason
  evidence_level
}
```

Evidence levels:

- `inventory_only`
- `static_distribution`
- `activation_calibrated`
- `functional_perturbation`
- `end_to_end_candidate`

Only `functional_perturbation` or stronger may authorize lowering a known
sensitive tensor below the conservative partition default.

The planner objective is:

```text
minimize packed_size + latency_cost
subject to:
  integrity == true
  required_capabilities preserved
  quality gates not crossed
  every precision decision evidence-backed
```

### 4.4 Quantizer and BitPacker

V0 candidate:

- symmetric group-wise Q8/INT8 for approved rank-2 talker matrices;
- real signed 8-bit storage;
- per-group FP16 or FP32 scales as required by the target runtime;
- deterministic rounding and byte-for-byte reproducibility;
- no zero-point unless the selected runtime contract requires asymmetric
  quantization.

Later candidates may add Q6 or Q4 only after a target runtime and its exact
packing contract are selected. A value range limited to four bits but stored in
one byte is not considered packed Q4.

### 4.5 RuntimeWriter

Quantization and packaging are separate.

A writer must be selected by the intended consumer:

- SafeTensors writer only if the pinned PyTorch/runtime kernels consume its
  quantized representation;
- GGUF writer only for a pinned same-family Qwen3-TTS runtime and matching
  talker/codec format;
- ONNX writer only after a faithful graph export exists and ONNX Runtime can
  execute all required CustomVoice capabilities.

No generic internal Parquet model output is part of v0.

### 4.6 CandidateValidator

Validation produces an immutable receipt containing:

- source and output hashes;
- exact quantization and packing manifest;
- target runtime identity and checksum;
- tensor coverage and untouched-tensor list;
- packed bytes and compression ratio;
- peak host RSS plus backend-specific memory evidence where available;
- load time, first-audio latency, real-time factor, and sustained behavior;
- corpus-level token, STT, speaker, expression, and acoustic comparisons;
- generated artifact hashes and human-confirmation bindings.

A healthy worker or non-empty WAV is not a quality pass.

## 5. Initial partition policy

This is a conservative starting policy, not a promotion decision.

| Partition / family | Initial treatment | Reason |
|---|---|---|
| Talker attention and MLP matrices | Q8 candidate | Largest repeatable matrix family; static entropy/error signal is strong |
| Talker norms, scales, small biases | BF16 | Minimal size benefit and possible numerical sensitivity |
| Text embedding | separate Q8 experiment | About 622 MB and highly valuable, but semantically sensitive |
| Code-predictor attention/MLP | Q8 after isolated perturbation | Discrete acoustic-code errors may accumulate |
| Code-predictor embeddings and heads | BF16 initially | Direct influence on generated speech-token streams |
| Speech tokenizer/codec | FP32 unchanged | Separate 682 MB acoustic model with heterogeneous convolution/codebook behavior |
| Codec convolution/quantizer families | diagnostic only | Static probe already exposed low-entropy/high-outlier counterexamples |

This policy provides a Q8 talker-first path without making codec quality an
uncontrolled variable.

## 6. Experiment arms

All arms use the same source hash, runtime, corpus, prompts, voices,
instructions, seeds, and output validation.

| Arm | Allocation policy | Purpose |
|---|---|---|
| A | Uniform eligible-matrix Q8 | Stable baseline candidate |
| B | Tensor-family/name heuristic | Measure value of simple architecture knowledge |
| C | Weight entropy and outlier diagnostics | Measure static diagnostic value |
| D | Entropy + activation + functional sensitivity | Test the proposed joint planner |

Arm D advances only if it demonstrates a reproducible Pareto improvement over
A and B. If C or D do not improve the frontier, entropy remains report-only.

## 7. Frozen validation corpus requirements

Before candidate comparison, freeze and hash a corpus containing:

- short and long natural Chinese;
- dates, numbers, units, abbreviations, and punctuation;
- mixed Chinese/English cases explicitly supported by the baseline;
- multiple accepted CustomVoice speakers;
- neutral, warm, serious, cheerful, sad, urgent, and restrained instructions;
- silence/pause and sentence-boundary cases;
- repeated deterministic trials for stability where seeds are honored.

Corpus text may be public or synthetic and must not contain private task,
contact, credential, or payment data.

Thresholds for STT, speaker consistency, expression adherence, token divergence,
and latency must be preregistered after measuring the frozen FP16 baseline and
before evaluating a quantized candidate. Thresholds cannot be chosen after
seeing candidate results.

## 8. Delivery plan

### Q0 — State and evidence freeze

Deliver:

- source asset manifest and hashes;
- model partition inventory;
- FP16 worker identity receipt;
- frozen corpus proposal and baseline measurement preregistration.

Exit gate:

- no ambiguous model or runtime identity;
- codec and talker assets independently accounted for.

### Q1 — Report-only static diagnostic CLI

Deliver:

- standalone Rust CLI or isolated crate;
- SafeTensors header/mmap reader;
- multiscale entropy, outlier, and simulated Q8/Q4 error reports;
- deterministic JSON schema and golden fixtures;
- no writer and no dependency on PyTorch.

Exit gate:

- bounded memory on both 3.83 GB and 682 MB files;
- stable results across repeated runs;
- malformed offsets/dtypes fail closed.

### Q2 — Calibration and sensitivity capture

Deliver:

- opt-in Python adapter inside the existing isolated Qwen environment;
- frozen-corpus activation statistics;
- one-layer-at-a-time fake-quant perturbation harness where technically
  accessible;
- token/code-stream divergence receipts.

Exit gate:

- hooks do not change default worker behavior;
- baseline output is reproducible enough to preregister thresholds;
- missing internal boundaries produce an explicit unsupported result.

### Q3 — Q8 planner and packer

Deliver:

- experiment arms A through D as deterministic plans;
- real Q8 bit packing for approved tensors;
- untouched tensor preservation;
- exact tensor coverage and size receipts.

Exit gate:

- output format has a pinned consumer;
- round-trip or runtime load integrity succeeds;
- no tensor silently falls back or changes dtype.

### Q4 — Isolated candidate worker

Deliver:

- separate owner-only Worker v1 socket;
- truthful engine/model/precision/capability report;
- no automatic fallback and no replacement of FP16/MPS;
- synth-file comparison receipts.

Exit gate:

- exact output artifact passes the preregistered automated gates;
- failures leave the FP16 service untouched.

### Q5 — Human and resource acceptance

Deliver:

- exact-artifact playback A/B;
- human intelligibility, naturalness, speaker, and expression decisions;
- load, RSS/backend memory, latency, RTF, and repeated-utterance stability.

Exit gate:

- owner explicitly accepts a named candidate artifact and aggregate reliability;
- promotion remains a separate decision.

### Q6 — Lower-bit research

Only after Q8 acceptance:

- 6-bit/5-bit/4-bit group-size experiments;
- selective higher precision for code predictor, embedding, and outlier-heavy
  tensors;
- codec experiments in a separate axis;
- optional prebuilt runtime profiles for lower-resource nodes.

INT2 is outside the initial roadmap.

## 9. Stop conditions

Stop or retain report-only status if:

- no runtime can consume the packed output;
- speech-token or audio comparison boundaries cannot be observed;
- entropy-guided allocation does not improve the Q8 Pareto frontier;
- expression or speaker controls are silently lost;
- codec changes dominate quality regressions;
- memory savings are only file-size savings and do not reduce runtime
  residency;
- the work would require replacing the accepted worker before candidate
  acceptance.

## 10. Next authorized slice

This document did not authorize implementation by itself. The owner separately
authorized Q0 and Q1 after reviewing the design; their result is linked above.

Q0 and Q1 are now implemented: manifest, preregistration, and a report-only
static diagnostic CLI with no model writer and no runtime wiring. Q2 baseline,
activation calibration, token-boundary observation, and one fail-closed
functional-sensitivity smoke are now complete.

The next admissible design slice is control-only raw-logit reproducibility:
finite log-domain metrics, repeated greedy controls, and localization of the
talker/head-0 variation. It must not apply fake quantization. Any further
fake-Q8 execution requires a new frozen policy, a new persistent one-shot
claim, and a separate gate after the control distribution is understood.
