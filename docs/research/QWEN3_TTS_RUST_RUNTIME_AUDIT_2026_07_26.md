# Qwen3-TTS Rust Runtime Audit

Date: 2026-07-26

Status: source/build gate passed; real-model inference gate incomplete

## Decision

Use `danielclough/qwen3-tts-rs` / `qwen_tts_cli 0.1.1` as the first
disposable pure-Rust Qwen3-TTS pilot.

Keep the existing Python Qwen3 backend as the reference implementation. Do not
replace it, add a production dependency, or enable a Rust backend by default
until real audio has passed the same synthesis, intelligibility, playback, and
provenance gates.

## Candidates reviewed

### `danielclough/qwen3-tts-rs`

- Pure Rust inference on Candle.
- Published as `qwen_tts` and `qwen_tts_cli` 0.1.1.
- Repository metadata matches the crates.io package.
- MIT OR Apache-2.0 source license, committed license files, and committed
  `Cargo.lock`.
- macOS Metal/Accelerate build and test jobs are declared upstream.
- Local Apple Silicon checks passed:
  - `cargo check --locked --workspace --features metal,accelerate`
  - `cargo test --locked --workspace --features metal,accelerate --lib`
  - 116 tests passed.
- A locked release CLI built as arm64 and linked Metal and Accelerate.

Selected for the disposable pilot.

### `TrevorS/qwen3-tts-rs`

- Pure Rust inference on Candle and a broad feature surface.
- Local `metal,accelerate` source build passed.
- The project describes itself as experimental rather than production-ready.
- No committed `Cargo.lock`, no package repository metadata, and the manifest,
  README changelog, and similarly named crates.io package do not form one
  unambiguous release provenance chain.

Useful as an implementation reference, but not selected as the first runtime
dependency candidate.

### `second-state/qwen3_tts_rs`

- Apple Silicon path uses MLX through an `mlx-c` submodule.
- Default backend remains `tch`/libtorch.
- Model preparation still invokes Python tooling to generate tokenizer files.
- The inspected checkout had no Rust test files and contains a broad unsafe FFI
  surface for MLX.

Not selected for the first pilot.

## Upstream defect found

`qwen_tts 0.1.1` constructs both Hugging Face clients with `Api::new()`.
In `hf-hub 0.4.3`, that constructor uses the default global cache and ignores
`HF_HOME`; environment-aware behavior requires
`ApiBuilder::from_env().build()`.

The defect was reproduced: a supposedly isolated run wrote into
`~/.cache/huggingface`. The process was stopped and the exact newly created
model cache was moved into the disposable pilot directory. No global model
cache from the run remains.

A disposable two-file patch changed both model and tokenizer clients to
`ApiBuilder::from_env().build()`. After the patch:

- all 116 tests still passed;
- the release CLI rebuilt successfully;
- download data was written under the pilot-specific `HF_HOME`;
- the corresponding global cache path remained absent.

This patch must be carried locally or accepted upstream before Agent-Bridge may
invoke the Rust CLI with a cache-isolation claim.

## Incomplete real-model gate

The official `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` model is Apache-2.0 and is
the selected smallest CustomVoice validation target.

The first isolated download advanced only about 3 MB per minute. It was stopped
at approximately 8 MB rather than holding the task for several hours. No model
load, Metal inference, WAV output, STT verification, playback, or human
audibility claim was made.

## Required next gate

1. Fetch the official model into a disposable, explicit local directory using
   a resumable downloader with recorded revision and file checksums.
2. Run the patched arm64 CLI with `--device metal --dtype f16`.
3. Generate a short fixed Chinese utterance with a fixed seed.
4. Record wall time, peak memory, output SHA-256, sample rate, channels, and
   duration.
5. Run file-level STT as an intelligibility check.
6. Play the named artifact and obtain human audibility confirmation.
7. Only then design a default-off `qwen3-rust` Agent-Bridge backend. Keep
   generated models and audio outside Git.

