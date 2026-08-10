# Qwen3-TTS Q2 one-shot fake-Q8 functional-sensitivity result

Date: 2026-07-27  
Status: `BLOCKED_CONTROL_LOGIT_REPLAY_NONDETERMINISM`  
Promotion: `NOT_AUTHORIZED`

## Result

The exact one-module/one-case fake-Q8 smoke executed once and consumed its
persistent authorization claim. The isolated process restored every Parameter,
the target runtime-weight bytes, the target forward method, model files,
inference-critical source files, and the complete pinned runtime package trees.
It did not call the accepted Worker, enter the codec decoder, produce audio,
write a model, create a packed candidate, or change runtime routing.

The result is intentionally fail-closed. Control-before and control-after
generated the same 23 × 16 speech-code matrix, but their raw talker logits and
code-predictor head 0 logits were not byte-identical. Heads 1 through 14 were
byte-identical. Because the frozen gate required exact control code and logit
replay, the fake-Q8 divergence cannot be attributed solely to the quantized
proxy and is not an acceptance result for this tensor or precision.

## Frozen execution identity

| Item | SHA-256 |
| --- | --- |
| Functional-sensitivity policy | `43b07f5f30bdc5aad7569b1d3412ea44619bd460fa7925cc037384291e86addd` |
| One-shot execution gate | `1d9f7f98ce628b6227c53c4843708dc3a84da255c638190e5a1ed2f489105f15` |
| Gate evaluator | `d64e16e1887cc527dc0b794ac6014fae580ffaec15ab3bf3f600a87d7faf38e8` |
| Executed harness | `a10f1945376239b8fe4cf0c1ba990e5430b11cf998e9164877da89080127d735` |
| Persistent one-shot claim | `29a1186837827f6d449166f879690821681c01bcc02f891236f2b9f2e3c90a99` |
| Immutable result | `cb4c98524bd4cdfae6878b04110c907b2bef3cd519f246493e59a92d03c6f3b3` |

The trial identity is
`qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001`. Its claim and
result are owner-only files in
`~/.local/state/agent-bridge/qwen3-evaluation-ledger/`. The claim was created
with exclusive create and both the file and parent-directory entry were
synchronized. It is never automatically deleted, so this gate cannot be
replayed.

The frozen target was
`talker.model.layers.6.mlp.gate_proj.weight`, shape `[6144, 2048]`, source
BF16/runtime FP16. The single corpus case was
`zh-short-neutral-serena`.

## Quantization proxy

The proxy used exact source BF16 values, row-local group-128 symmetric Q8,
f64 `max_abs / 127` scales, half-away-from-zero rounding, range `[-127, 127]`,
and FP16 dequantization. It did not store scales or pack a model.

| Measurement | Value |
| --- | ---: |
| Groups | 98,304 |
| Zero groups | 0 |
| Changed FP16 elements | 12,198,730 / 12,582,912 |
| Source/dequant NRMSE | 0.0066684252 |
| Mean absolute error | 0.0001022612 |
| Maximum absolute error | 0.0011084249 |
| Q8 integer hash | `4075b79074a4e371127ee1974a8cfed41f9b60c7268afe4b33f75968275ea31d` |
| Dequant FP16 hash | `ca808eb5cb68058d6514092bf224f5fdb2d1e86880c0096f6501d8a9a0d70293` |

The temporary forward proxy was exercised 23 times with exact MPS/float16,
input dimension 2,048. It was an ordinary Tensor closure, never a Parameter or
state-dict entry.

## Control replay

Both control passes produced 23 time steps and 16 codebooks with canonical
code hash
`ea117b54d9181162a585af5a99f935ff385377adbac359272834863ca6d7e951`.
Every code element, frame, and codebook matched.

The stricter canonical shape/dtype/raw-byte logit replay failed:

- talker logits differed:
  `26b9630c…` versus `370a9078…`;
- code-predictor head 0 differed:
  `10050b79…` versus `e92c3f2a…`;
- code-predictor heads 1 through 14 matched exactly.

This is compatible with small MPS/float16 prefill-path numeric variation that
does not cross the greedy code decision boundary, but that explanation remains
a hypothesis until a separately frozen control-only stability study measures
the variation. The receipt does not retain full logits, so their baseline
magnitude cannot be reconstructed post hoc.

## Fake-Q8 observation, not acceptance

The fake pass produced 22 time steps rather than 23. Against control over the
22-frame overlap:

- first-codebook agreement: `0.681818`;
- full-frame agreement: `0.409091`;
- element mismatch fraction: `0.522727`;
- common exact prefix: 9 frames;
- first divergent frame: 9;
- first-codebook normalized edit distance: `0.304348`.

Frame-aligned talker logits showed mean control-to-fake KL `1.221821`, top-1
agreement `0.636364`, top-8 retention `0.772727`, and centered-logit NRMSE
approximately `1.0`.

The initial code-predictor Jensen-Shannon calculation underflowed and emitted
`NaN`; that field is invalid and must not be used. Its occurrence does not
change the fail-closed status because the independent control-logit replay had
already failed. The literal `NaN` also makes this immutable receipt non-strict
RFC 8259 JSON, so strict parsers may reject it. Other evidence remains
hash-bound and readable with the Python/tolerant parser used for this audit.
A future metric implementation must use log-domain masking or another finite
formulation and serialize with non-finite values forbidden.

These fake-pass values are retained only as an observation that motivated the
next diagnostic. They do not prove that the target is Q8-sensitive because the
exact raw-logit control precondition was not met.

## Restoration and non-interference

All restoration gates passed:

- 404 Parameters / 1,916,676,352 elements retained the exact identity,
  storage, dtype/device, stride, version, and manifest hash;
- 404 state-dict keys retained the exact key hash;
- target runtime-weight hash remained
  `2b663471b103143c21d2bc17571af34570757f681472bbbcb4bb0a5ad4f844c6`;
- the full 15-entry model tree remained
  `5eef30b3256b0765577b6380df5161a86fab99dfdf024424af429a119586b0cf`;
- the 2,881-entry qwen/Transformers/SafeTensors runtime tree remained
  `142afb08e02780000655b73559ed3ec877c6e6630e8e75e753f3e07e69f9b11a`;
- all generate/decode overrides and raw-logit hooks were removed;
- actual codec decode calls, returned samples, audio writes, model writes,
  candidate creation, and Worker-socket calls were all zero.

The accepted Worker process and socket identity remained PID `55820`, with its original
`2026-07-27 02:19:46` start time and socket inode `45306340`.
This is non-interference evidence, not a separate live Worker health or
physical-audio acceptance test.

The isolated process completed in 16.50 seconds with maximum RSS
5,029,150,720 bytes, peak footprint 6,340,462,656 bytes, and zero swaps.

## Next gate

Do not rerun fake-Q8 under this consumed gate and do not create a Q8 candidate.
The next bounded target is a new, control-only raw-logit stability design:

1. freeze a numerically finite logit-summary implementation and reject
   non-finite JSON serialization;
2. run one cold plus five warm greedy controls without any proxy, synchronizing
   MPS explicitly at each trial boundary;
3. retain per-call input/output hashes and bounded deltas so variation can be
   localized to talker prefill, generated rows, terminal decision, predictor
   head 0 prefill, or heads 1–14 cached generation;
4. compare all control pairs using changed-element fraction, absolute and ULP
   deltas, centered NRMSE, top-1/top-8, and decision margins while requiring
   exact length/EOS/all-codebook replay;
5. classify each path as `BIT_EXACT`,
   `NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE`, or `UNSTABLE`, then
   preregister a tolerance only if the repeated distribution supports one;
6. require a new one-shot authorization before any further fake-Q8 trial, and
   compare future effects only before trajectory divergence and against the
   frozen control envelope.
