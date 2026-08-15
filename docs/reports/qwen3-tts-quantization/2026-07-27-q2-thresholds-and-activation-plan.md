# Qwen3-TTS Q2 thresholds and activation-plan result

Date: 2026-07-27  
Status: `Q2_REFERENCE_EVIDENCE_PARTIAL_FAIL_CLOSED`

## Landed

- Frozen candidate-comparison thresholds:
  `scripts/eval/fixtures/qwen3_tts_quantization_thresholds_v0.json`.
- Fail-closed evidence checker: `scripts/eval/qwen3_quant_threshold_gate.py`.
- Fixed Whisper reference collector: `scripts/eval/qwen3_stt_reference.py`.
- Frozen paired A/B listening protocol:
  `scripts/eval/fixtures/qwen3_tts_blinded_review_protocol_v0.json`.
- Default-off activation plan generator:
  `scripts/eval/qwen3_activation_probe_plan.py`.

Threshold contract SHA-256:
`2b37447912a7e5af68ab1db724689fad8065c6ccba61a7609e6118dde63cc56d`.
Blinded review protocol SHA-256:
`3851aeb87cdb04a62b74b02eab6b2ea5cd7f6c823ff48cad41698fb8f89f034b`.

## Reference evidence

Three complete FP16/MPS runs produced 48/48 readable WAVs. Their report hashes
are:

1. `b2f4fecf12d7257029cedf5ea92f04574a85fa1dcb6b53c7d77d23b9bb2529a1`
2. `2c4e383d243f60358d009e7446f6a4c00f9530cd40109c834a68963ed407b167`
3. `deeefbd89f29e0f051b10ec2fd9c10f3f03fa45fe612adcecab8e97808d1a490`

Run median RTF values were 1.514, 1.406, and 1.432. Output duration across all
runs ranged from 1.68 to 14.88 seconds. The current worker does not support a
generation seed, so these repetitions measure the sampled baseline rather than
claiming byte-deterministic speech.

Whisper `base`, Chinese, fixed-normalization reference completed for 16/16
artifacts. Mean CER was 0.1002, median 0.0, and maximum 0.5455. This reference is
for paired candidate deltas only; its absolute CER is not a human intelligibility
claim. STT report SHA-256:
`e5e6868604ea3e31c4487247c513e6bab5bd873d89187fe63d8f9433f7672942`.

## Activation-plan evidence

The generator considered only statically diagnosed rank-2 talker attention and
feed-forward/projection tensors. It excluded the codec, text/code embeddings,
code-predictor heads, norms, and tensors without diagnostics. There were 234
eligible modules; the bounded plan selected 96. Two independent generations
were byte-identical with SHA-256
`41f286cd48b0377d445655068742af72c5bef4c6b987ced9e2c1efce3a7b6f82`.

The plan retains no full activations, caps sampling at 4,096 values per module
and 256 MiB host memory, and requires detached CPU float32 summary statistics.
It has not loaded a second model or attached hooks yet.

## Current gate (superseded by follow-up evidence below)

The pre-candidate gate has no baseline-integrity failures but remains
`BLOCKED_PENDING_REFERENCE_EVIDENCE`. Its single remaining blocker is an
independent speaker-consistency and expression-adherence reference metric.
Candidate generation, runtime wiring, fallback, and promotion remain false.

The next bounded step was to select and pin an offline speaker/emotion evaluator
and measure the three FP16 reference runs. That work is now recorded below; the
next admitted action is still a separate-process activation calibration subset,
not quantized-weight writing.

## Evaluator-pinning readiness (follow-up)

The separate Python 3.11 evaluator environment now passes an actual
`from funasr import AutoModel` probe. The preflight is deliberately executed by
the supplied interpreter rather than trusting the caller process:
`scripts/eval/qwen3_evaluator_preflight.py`.

`scripts/eval/qwen3_evaluator_model_pin.py` requires two complete, explicit
local snapshots before any evaluator can be invoked: the selected
`chenxie95/emotion2vec_plus_large` mirror and
`damo/speech_campplus_sv_zh-cn_16k-common`. It hashes every regular file and
fails closed on a missing anchor or incomplete snapshot. The emotion snapshot is
now complete; the speaker snapshot remains absent. Neither tool downloads,
loads, wires, or promotes a model; both keep candidate generation and runtime
promotion false.

## Emotion reference evidence (follow-up)

The complete `chenxie95/emotion2vec_plus_large` snapshot was pinned with
`model.pt` SHA-256
`be501a01f26fcdc7663a062dff86af839afbaef7c4de32f5e42d7e1ad2784da4`.
`scripts/eval/qwen3_emotion_reference.py` then ran the pinned model on CPU over
the frozen first FP16 run's 16/16 WAV artifacts. The immutable report is
`/private/tmp/ab-qwen3-emotion-reference.3ZoJMo/report.json`, SHA-256
`06260f7d7aac25123c1a0a3d3c1eb9a589ce2d2d0f8e62ae150ad68b0f93e63b`.

Top categorical outputs were neutral 8, happy 6, surprised 1, and angry 1.
These are a paired candidate reference only. They do not establish instruction
adherence by themselves, speaker consistency, human naturalness, or a promotion
right.

## Speaker reference and candidate-review readiness (follow-up)

The complete `iic/speech_campplus_sv_zh-cn_16k-common` CAM++ snapshot passed
local FunASR embedding extraction. Its pinned weights are
`campplus_cn_common.bin`; three FP16 runs produced 192-dimensional embeddings
for every frozen artifact. The speaker reference receipt is
`/private/tmp/ab-qwen3-speaker-reference.ak0rgV/report.json`, SHA-256
`bb70229e7198b3a583404a25cafbed45e7b5cb434a932cfa0fd219e72987ed1b`.
It contains 32 first-run-to-repeat cosine comparisons: minimum 0.3402 and mean
0.7871. This measures cross-run consistency for each same case, not identity
against a separately enrolled named voice.

The speaker receipt and three emotion receipts are bound by
`/private/tmp/ab-qwen3-speaker-expression-reference.UBwucz/report.json`,
SHA-256 `c6d4de41ab5be0556f8ce8810ae2f5bb76539b5f5859eb590f7735f5f4f89e30`.
The threshold fixture now pins that receipt. With all three FP16 reports, the
Whisper reference, the bound receipt, and the frozen blinded-review protocol,
`qwen3_quant_threshold_gate.py` returned `READY_FOR_CANDIDATE_REVIEW` with no
failures or blockers. Its authorization fields remain false: this only admits
the next offline candidate-review preparation, never runtime wiring, fallback,
or promotion.

## Activation plan v1 and full calibration (follow-up)

The earlier 96-of-234 plan and hash above are historical and superseded. The v1
generator excludes all code-predictor matrices and uses rotating layer/role
stratification over 196 eligible talker attention/MLP matrices. The frozen
96-module plan covers all 28 talker layers and has SHA-256
`d87deeeadf81aaba2d010bded7c60e8b0bd8f74419b6e6a132a46d1d9fd2fb12`.

The separate-process full activation capture completed all 96 × 16 observations
with zero empty activations and zero sampled nonfinite values. The independent
gate returned `READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN` while leaving fake
quantization, weight writing, candidate generation, runtime wiring, and
promotion false. See
[`2026-07-27-q2-activation-calibration.md`](2026-07-27-q2-activation-calibration.md)
for hashes, resource measurements, and the next admitted boundary.
