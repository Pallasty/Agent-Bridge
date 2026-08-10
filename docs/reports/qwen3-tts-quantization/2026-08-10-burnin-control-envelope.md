# Qwen3-TTS burn-in separated control envelope

Date: 2026-08-10

## Result

The revised control gate passed. One offline process loaded the verified Qwen3-
TTS CustomVoice model once, executed two non-measured MPS FP16 burn-in calls
(`B0_burn_in`, `B1_burn_in`), then captured six measured calls (`M0_measured`
through `M5_measured`).

All measured paths were `BIT_EXACT` across all 15 pairwise comparisons:

- talker generated rows;
- talker terminal decision row;
- predictor head 0;
- predictor heads 1 through 14.

All six measured code matrices were exactly `23 x 16`, with canonical SHA-256
`ea117b54d9181162a585af5a99f935ff385377adbac359272834863ca6d7e951`. Cleanup,
pre-codec interception, length, and finite-value boundaries passed. No audio was
written or played, no worker socket was used, and no model or quantized weight
was mutated.

## Receipt

The owner-only receipt is outside the repository and retains no full logits or
audio:

- receipt SHA-256: `b49daac8b537395820de038a41fde828b951f2af214aaf7d0dfe154f444f7f57`
- process peak resident memory: `5,020,057,600` bytes
- Python `3.12.13`, PyTorch `2.13.0`, qwen-tts `0.1.1`, MPS, FP16, offline

## Admission boundary

This result freezes the control envelope only. It permits the next separately
authorized gate: exactly one fake-Q8 sensitivity trial using the existing
read-only interception path. It does not permit quantized-weight writing,
runtime replacement, worker promotion, deployment, or broad calibration.
