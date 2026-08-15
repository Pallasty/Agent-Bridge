# Qwen3-TTS control-logit stability gate

Date: 2026-08-10

## Outcome

The frozen C0 cold plus C1-C5 warm control gate is **not admitted**. No fake-Q8
trial, quantized-weight write, worker replacement, runtime wiring, or deployment
was authorized or performed.

Two independent six-trial processes produced the same boundary pattern. In the
second process:

- all six realized code matrices were exactly equal at `23 x 16`, with canonical
  SHA-256 `ea117b54d9181162a585af5a99f935ff385377adbac359272834863ca6d7e951`;
- all trial cleanup and pre-codec interception checks passed;
- the talker terminal row and predictor heads 1-14 were bit-exact across every
  pair;
- predictor head 0 differed only between C0 and later trials, then was bit-exact
  across C1-C5;
- the talker generated rows changed only at row 0; C0 differed from every later
  trial, C1 differed from C2-C5, and C2-C5 were mutually bit-exact.

This is evidence that the current MPS FP16 observation path has a two-call
startup transition before full raw-logit stability. It is not evidence that
quantization is safe, and it does not establish the cause of the transition.

## Evidence

The second owner-only receipt was written outside the repository and retains no
full logits or audio:

- receipt SHA-256: `da95875f9386dfffe489d04c0741c6c81446c17c2de2d5e775daa147b2bfdecb`
- receipt mode: `0600`
- process peak resident memory: `5,017,714,688` bytes
- Python `3.12.13`, PyTorch `2.13.0`, qwen-tts `0.1.1`, MPS, FP16, offline

The first independent receipt had SHA-256
`a40b65beb63f4d4b50f6377cede55a9f77e4e974f2d40c10f971d464164f37bb`
and reproduced the same high-level classification.

## Next gate

Freeze a revised control protocol with two explicitly non-measured burn-in calls,
followed by six measured controls in the same process. Admit a later fake-Q8
comparison only if all six measured controls are bit-exact for codes, length,
talker generated and terminal rows, and predictor heads 0-14. The revised gate
must remain offline, pre-codec, non-writing, worker-independent, and separately
authorized from any fake-Q8 execution.
