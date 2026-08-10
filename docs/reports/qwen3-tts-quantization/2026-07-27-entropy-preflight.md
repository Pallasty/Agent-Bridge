# Qwen3-TTS entropy-guided quantization preflight

Date: 2026-07-27  
Status: `EVIDENCE_ONLY_DEFAULT_OFF`  
Scope: local Qwen3-TTS 1.7B CustomVoice baseline and read-only static analysis

## Result

Information entropy is useful as a predictor of local weight quantization error
for the Qwen3-TTS talker, but it is not sufficient to infer functional TTS
sensitivity or to assign bit widths directly.

The original ArrowQuant V2 normalized-entropy ordering carries signal. Its fixed
`INT8 / INT4 / INT2` thresholds do not transfer safely to this model.

No model was converted, no weights were written, no audio was synthesized, and
no running service was changed during this preflight.

## Current baseline

### Agent-Bridge

- Agent-Bridge MCP reports version `0.14.0`, build `e122fe1bbc80`.
- Local memory is available with the `gte-multilingual-base` 768-dimensional
  backend.
- The repository is dirty and diverged from `origin/master`
  (`ahead 3, behind 10`). This report does not authorize sync, staging, push, or
  deployment.

### Voice worker

The owner-local Worker v1 health probe returned:

```json
{
  "protocol": "ab.tts.worker.v1",
  "engine": "qwen3-pytorch",
  "state": "ready",
  "device": "mps",
  "dtype": "float16",
  "capabilities": ["custom_voice", "instruct", "zh"]
}
```

LaunchAgent `com.pallasting.agent-bridge.qwen3-tts` was running. The health
probe proves the selected worker identity and readiness only; this run did not
repeat synthesized-file STT or human playback acceptance.

### Model assets

Snapshot:

```text
/Users/pallasting/.cache/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master
```

Observed files:

| Partition | File size | Tensors | Stored dtype |
|---|---:|---:|---|
| Talker and code predictor | 3,833,402,552 bytes | 404 | BF16 |
| Speech tokenizer / codec | 682,293,092 bytes | 496 | FP32 |
| Complete snapshot | about 4.2 GiB | — | mixed |

The model config separates:

- a 28-layer, hidden-size-2048 talker;
- a 5-layer, hidden-size-1024 code predictor;
- a separately stored 12 Hz speech tokenizer/codec with 8-layer encoder and
  decoder Transformer components plus convolutional and residual-vector-
  quantization paths.

The largest single tensor is
`talker.model.text_embedding.weight`, approximately 622 MB in BF16.

This confirms that talker, discrete-code predictor, and acoustic codec need
separate precision policies.

## Static entropy experiment

### Method

The SafeTensors headers and tensor bytes were read through a read-only memory
map. For every rank-2-or-higher supported tensor with at least 4,096 elements:

1. sample up to 8,192 evenly spaced values;
2. compute normalized histogram Shannon entropy;
3. simulate symmetric per-tensor Q8 and Q4 reconstruction;
4. compute normalized reconstruction RMSE and an outlier ratio.

This is a distribution probe, not an inference-quality result. It does not
capture activations, Hessian/Jacobian sensitivity, speech-token drift, codec
behavior, or audible quality.

### Aggregate result

| Partition | Eligible tensors | Median H256 | Median Q4 NRMSE | Spearman H256 vs Q4 error |
|---|---:|---:|---:|---:|
| Talker | 267 | 0.8322 | 0.2265 | -0.9743 |
| Codec | 213 | 0.7759 | 0.2780 | -0.5009 |

For the talker, the entropy ranking strongly tracks local per-tensor Q4
reconstruction error: higher normalized histogram entropy generally coincided
with lower error. The codec shows a weaker and less stable relationship because
its convolutional, codebook, scale, and Transformer tensors have heterogeneous
distributions.

Representative samples:

| Tensor | H256 | Q8 NRMSE | Q4 NRMSE | Outlier ratio |
|---|---:|---:|---:|---:|
| text embedding | 0.8291 | 0.0123 | 0.2229 | 0.0007 |
| talker layer 0 attention Q | 0.7614 | 0.0201 | 0.3602 | 0.0038 |
| talker layer 0 MLP up | 0.8732 | 0.0096 | 0.1719 | 0.0004 |
| code predictor layer 0 attention Q | 0.7788 | 0.0158 | 0.2879 | 0.0024 |
| codec decoder pre-convolution | 0.2840 | 0.0808 | 0.6438 | 0.2369 |
| codec decoder first convolution | 0.5861 | 0.0454 | 0.5753 | 0.0510 |

The codec pre-convolution is a useful counterexample: low entropy, many
outliers, and high local Q4 error identify it as a likely precision-sensitive
candidate. This still does not prove that another high-entropy tensor is safe
for TTS output.

### Fixed-threshold falsification

ArrowQuant V2 maps normalized entropy below `0.5` to INT8, `0.5..0.7` to INT4,
and at least `0.7` to INT2. Applied to the actual Qwen3-TTS tensors:

| Partition / bins | INT8 | INT4 | INT2 |
|---|---:|---:|---:|
| Talker / 64 | 1 | 46 | 220 |
| Talker / 256 | 0 | 7 | 260 |
| Talker / 1024 | 0 | 2 | 265 |
| Codec / 64 | 33 | 68 | 112 |
| Codec / 256 | 23 | 36 | 154 |
| Codec / 1024 | 17 | 18 | 178 |

Rank ordering remained highly stable across bin counts, while the absolute
normalized value moved enough to change the bit-width bucket. Therefore:

- entropy percentile/rank is a viable feature;
- a universal normalized-entropy threshold is not;
- INT2 is not an admissible first candidate;
- module type, outliers, activation statistics, and functional perturbation
  evidence must constrain the planner.

## ArrowQuant V2 capability result

Reusable ideas:

- sharded SafeTensors inventory;
- layer-wise streaming and resumable receipts;
- bounded-memory scheduling and buffer reuse;
- sensitive-layer overrides and mixed-precision planning;
- calibration cache, SIMD kernels, and explicit fallback gates.

Non-transferable or incomplete pieces:

- diffusion timestep, beta-schedule, Markov-boundary, and transition optimizer
  assumptions;
- custom Parquet output, which no current Qwen worker consumes;
- INT4 and INT2 values stored as one byte per weight rather than genuinely
  packed values;
- cosine-only quality validation;
- current macOS test linkage, which still searches for an unavailable Xcode
  Python 3.9 library. `cargo check --lib --no-default-features` succeeds, while
  `cargo test --lib --no-default-features` does not link on this host.

## Decision

Proceed to a design-only, isolated `ab-qwen-quant` plan.

The first implementation slice, if separately started, is report-only static
inventory and entropy/outlier/reconstruction diagnostics. It cannot write a
candidate model or affect Worker v1.

The first candidate precision is genuinely packed Q8/INT8 for selected talker
matrix weights. The speech tokenizer/codec remains unchanged until separately
measured. INT4, runtime-adaptive repacking, worker replacement, and promotion
are later gates.

