# Qwen3-TTS quantization asset recovery

Status: `ASSETS_RECOVERED_ON_CURRENT_MASTER_DEFAULT_OFF`

## Recovery identity

- source checkout: `/Users/pallasting/Projects/agent-bridge`
- source HEAD: `44a4b2d043debf6fe3583d18cab54f3c5b6ba5aa`
- source condition: dirty/diverged; quantization assets were mostly untracked
- destination base: `acecfca46f0c9604b0e679b0623d63332530640c`
- destination branch: `codex/qwen-quant-asset-recovery-20260810`
- recovered asset files: 49
- recovered path+content aggregate SHA-256:
  `953b269c820dfdc39619575328d70155c3f6569a0639e53ebf4d576159a0d497`

The aggregate is SHA-256 over each recovered file's sorted relative path, a
NUL separator, its SHA-256, and a newline. It excludes the workspace membership
and lockfile changes made after recovery.

## Recovered scope

- `crates/qwen-quant`: read-only SafeTensors inventory and Q8/Q4 diagnostics;
- entropy-guided design and Q0/Q1/Q2 reports;
- frozen corpus, thresholds, calibration, activation and review policies;
- activation, evaluator, token-boundary and fake-Q8 scripts;
- corresponding Python and Rust tests;
- the isolated GGUF candidate probe.

The source checkout was not modified. The recovered crate is registered in the
current workspace and remains default-off.

## Current-master verification

- `cargo fmt -p ab-qwen-quant -- --check`: passed;
- `cargo clippy -p ab-qwen-quant --all-targets --locked -- -D warnings`: passed;
- `cargo test -p ab-qwen-quant --locked`: 4 passed;
- `python3 -m pytest -q tests/test_qwen3_*.py`: 58 passed.

The broader `cargo fmt --all -- --check` baseline remains red on unrelated
pre-existing current-master files. No unrelated formatting was changed as part
of this recovery.

## Boundary

No quantized model writer, packed Q8/INT8/INT4 artifact, runtime adapter,
worker replacement, deployment, model inference, or audio playback is included
or authorized by this recovery. The one-shot fake-Q8 result remains blocked by
control raw-logit replay nondeterminism.

## Next gate

Re-establish the C0 cold plus C1-C5 warm control-only raw-logit stability
envelope on the pinned FP16 model before authorizing another fake-Q8 trial or
implementing a packed Q8 writer.
