# Qwen3-TTS Q2 activation capture smoke

Date: 2026-07-27  
Status: `HISTORICAL_SMOKE_SUPERSEDED_BY_FULL_CALIBRATION`

[`qwen3_activation_capture.py`](../../../scripts/eval/qwen3_activation_capture.py)
loaded a separate local Qwen3-TTS model on MPS/float16, attached hooks to the
first eight planned talker MLP modules, and generated one short corpus case in
memory. It wrote no WAV, did not modify weights, and did not alter Worker v1.

All 8/8 planned module names resolved and each yielded the bounded 4,096-value
summary sample. Capture JSON SHA-256:
`24b8f455445622f99921b630bffe3fc207df7f3e0fe5c6089f43daf42cd2aecf`.

This historical smoke validated the initial hook seam and isolation only. Its
8-module plan and receipt are superseded by the frozen v1 plan, resource ladder,
and full 96-module × 16-case result in
[`2026-07-27-q2-activation-calibration.md`](2026-07-27-q2-activation-calibration.md).
The earlier speaker/emotion blocker was also resolved later by pinned
emotion2vec and CAM++ FunASR reference receipts. No quantized candidate is
authorized by either result.
