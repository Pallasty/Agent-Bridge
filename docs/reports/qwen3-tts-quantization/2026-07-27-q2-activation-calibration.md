# Qwen3-TTS Q2 activation calibration and perturbation-scope result

Date: 2026-07-27  
Status: `READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN_DEFAULT_OFF`

## Result

The frozen 96-module activation plan completed all 16 frozen corpus cases in a
separate MPS/float16 Qwen3-TTS process. All 1,536 module/case observations
retained exactly 4,096 finite sampled values. There were no unresolved
parameters, empty activations, sampled NaN/Inf values, weight mutations, WAV
writes, candidate writes, or runtime changes.

The accepted Worker v1 remained on its original PID and socket throughout this
offline capture. This result admits only the design of a one-module-at-a-time
fake-Q8 functional-sensitivity experiment. It does not admit fake-quant
execution, quantized-weight writing, a runtime candidate, fallback, deployment,
or promotion.

## Landed controls

- Frozen activation plan:
  `scripts/eval/fixtures/qwen3_tts_activation_probe_plan_v1.json`.
- Frozen calibration policy:
  `scripts/eval/fixtures/qwen3_tts_activation_calibration_policy_v0.json`.
- Frozen resource-ladder receipt:
  `scripts/eval/fixtures/qwen3_tts_activation_resource_ladder_v0.json`.
- Read-only capture:
  `scripts/eval/qwen3_activation_capture.py`.
- Independent fail-closed gate:
  `scripts/eval/qwen3_activation_gate.py`.
- Non-writing perturbation-order planner:
  `scripts/eval/qwen3_q8_scope_plan.py`.

The v1 plan selects 96 of 196 eligible rank-2 talker attention/MLP matrices.
Its rotating layer/role stratification covers all 28 talker layers and excludes
the codec, text embedding, all code-predictor matrices, norms, and scale/bias
tensors. Every selected tensor is bound at runtime by exact parameter name,
module `weight` object identity, shape, element count, source dtype, and runtime
dtype.

## Frozen identities

| Evidence | SHA-256 |
| --- | --- |
| Q0/Q1 static report | `6999f67da3b3ac6319cdc68049cba9e5ac78e5f98dd252615877db7354178e93` |
| Frozen 16-case corpus | `9193f6e5359fcf3ecd9c0a5a2726886908ffa3a266ab7597f283629e710a7afd` |
| Activation plan v1 | `d87deeeadf81aaba2d010bded7c60e8b0bd8f74419b6e6a132a46d1d9fd2fb12` |
| Calibration policy | `9cf235640d5f8960393edef6600b137faaa939c3451bd46b91246686377da061` |
| Resource-ladder receipt | `8e9a3f4ec9596ea142940a2857c16122c3c73baeb47975e382a6f15c4e34f7d2` |
| Full activation capture | `365b9f9e9b7cd5a3b9890945ed8f4428cc9aa51b1c3dc3a448b1bdf2847fb4b4` |
| Activation gate receipt | `369f7af4d964a5d285be8dd00865faf107060e8973003611c9329821113da8c9` |
| Fake-Q8 perturbation scope | `4a4abee2cdc336ea68af14413dacb7f91ea3a2c039ce51a058fdd5a37e97e7ec` |

The model bindings are:

- talker `model.safetensors`: 3,833,402,552 bytes,
  SHA-256 `38b1d5971bdbd982b561cccec982669a53b0537c3cf5e9bd4778ed07bb2f5137`;
- speech-tokenizer codec: 682,293,092 bytes,
  SHA-256 `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258`.

## Resource ladder

The preregistered 8 → 24 → 48 → 96-module ladder completed sequentially with
zero swaps:

| Modules / cases | Case class | Status | Real time | Max RSS | Peak footprint |
| --- | --- | --- | ---: | ---: | ---: |
| 8 / 1 | short neutral | read-only smoke | 10.37 s | 5.02 GB | 6.33 GB |
| 24 / 1 | long technical | read-only smoke | 24.75 s | 5.02 GB | 8.05 GB |
| 48 / 1 | long narrative | read-only smoke | 24.00 s | 5.02 GB | 7.30 GB |
| 96 / 16 | full frozen corpus | full capture | 210.47 s | 5.02 GB | 10.15 GB |

These four report hashes and measurements are bound by the frozen
resource-ladder receipt above. The activation plan's 256 MiB host-memory field
is a retained summary-state cap; it is not a total model-process RSS or peak
footprint claim.

The full report is
`/private/tmp/ab-qwen3-activation-calibration-v1-final.VZnBz7/report.json`
(2,466,820 bytes). It accounts for 6,291,456 retained sample values over
533,770,240 activation elements seen. Per-observation hook calls ranged from 24
to 167. Runtime identity was Python 3.12.13, PyTorch 2.13.0, `qwen-tts` 0.1.1,
MPS, float16.

The capture deliberately reports `sample_min` and `sample_max`; these are not
full-activation extrema. Its entropy is normalized over the bounded per-module,
per-case reservoir rather than fixed global histogram edges. These values are
valid as frozen within-run ranking features, not universal activation
distributions.

## Independent gate

`qwen3_activation_gate.py` verified the exact plan, corpus, source assets,
parameter bindings, case ordering, module ordering, sample floor, output
shape/dtype digests, nonfinite count, MPS/float16 and pinned runtime identity,
the hashed 8/24/48/96 resource ladder, and all safety fields. It returned:

```text
READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN
planned_modules=96
captured_cases=16
module_case_observations=1536
minimum_samples_per_module_case=4096
failure_count=0
```

The immutable receipt is
`/private/tmp/ab-qwen3-activation-gate-v0-sealed.AQEhRf/report.json`.

## First functional-sensitivity scope

The non-writing planner ranked the 96 calibrated modules using the frozen joint
risk policy and selected 48 for the first one-module-at-a-time fake-Q8
perturbation tranche. The other 48 remain explicit FP16 controls. All 96
qualified; the selected tranche spans 25 of 28 talker layers.

The planner's size calculation is hypothetical only: 771,751,936 source bytes
would become an estimated 391,905,280 packed bytes under group-128 Q8 with
float16 scales, a projected 379,846,656-byte (49.21875%) reduction for that
tranche. No packing or model mutation occurred.

The scope receipt is
`/private/tmp/ab-qwen3-q8-perturbation-scope-v0-sealed-final.bNn7y8/report.json`.
It uses `eligible_for_future_perturbation_design` and
`proposed_mode_if_separately_authorized` fields, plus an explicit authorization
object in which fake-quant execution, weight writing, candidate generation, and
runtime wiring/promotion are all false.

## Next admitted target

Design and test a default-off, separate-process perturbation harness that
changes exactly one selected module at a time, restores the untouched FP16
weight before the next trial, and emits explicit functional divergence
receipts. The harness must first prove that it can observe the relevant
speech-token/code boundary; if that boundary is unavailable, it must record an
unsupported result rather than substitute waveform quality for token evidence.

## Subsequent result

That target was later implemented behind a separate persistent one-shot gate.
The token/code boundary was observed, and the single fake-Q8 trial restored all
state, but exact control raw-logit replay failed while control speech codes
remained exact. The fail-closed result and revised next gate are recorded in
[`2026-07-27-q2-functional-sensitivity-one-shot.md`](2026-07-27-q2-functional-sensitivity-one-shot.md).
