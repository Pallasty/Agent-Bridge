# Qwen3-TTS Rust Runtime Audit

Date: 2026-07-26 (updated 2026-07-27)

Status: disposable 1.7B synthesis, intelligibility, playback, and human
audibility gates passed; production integration remains intentionally closed

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

## Real-model gate

The official `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` model is Apache-2.0 and is
the selected smallest CustomVoice validation target.

The first isolated download advanced only about 3 MB per minute. It was stopped
at approximately 8 MB rather than holding the task for several hours. No model
load, Metal inference, WAV output, STT verification, playback, or human
audibility claim was made.

### Download-path probes

The official Hugging Face revision was resolved and pinned to:

`85e237c12c027371202489a0ec509ded67b5e4b5`

Its two LFS objects are:

- `model.safetensors`: 1.8 GB, SHA-256 prefix `bc3c7e785e`
- `speech_tokenizer/model.safetensors`: 682 MB, SHA-256 prefix `836b7b357f`

Three resumable paths were tested without completing either object:

1. `git-lfs` downloaded both objects at roughly 18-20 MB per minute.
2. `huggingface_hub 1.24.0` with Rust `hf_xet` and high-performance mode
   initially reached 67 MB, then held multiple established connections without
   further file growth.
3. The Qwen-official ModelScope mirror transferred the main model at roughly
   0.2 MB/s and the speech tokenizer at roughly 0.7-0.8 MB/s.

All processes were stopped rather than occupying the foreground for hours.
Partial data remains only under the disposable pilot root. The exact global
Hugging Face model-cache path was checked after each attempt and remains absent.

No fresh aio2 or tb14 Agent-Bridge presence was available at the time of the
probe, so no remote download was dispatched based on stale node records.

### 1.7B ModelScope snapshot: accepted for the disposable pilot

The following completed local snapshot was checked without modifying or
relocating it:

`/Users/pallasting/.cache/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master`

The manifest reports `tts_model_size=1b7` and `tts_model_type=custom_voice`.
The complete file hashes match the corresponding Hugging Face LFS OIDs:

- `model.safetensors`: 3,833,402,552 bytes,
  `38b1d5971bdbd982b561cccec982669a53b0537c3cf5e9bd4778ed07bb2f5137`
- `speech_tokenizer/model.safetensors`: 682,293,092 bytes,
  `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258`

The Rust arm64 CLI loaded the model on Metal and generated the fixed Chinese
utterance successfully. The first attempt used `Serena` and was rejected by
the 1.7B CLI's lowercase speaker registry; retrying with `serena` succeeded.
This is now represented as the explicit `1.7b-customvoice` profile in the
offline gate, rather than changing the existing 0.6B profile implicitly.

Gate evidence:

- elapsed inference: 5.732 seconds;
- WAV: 24,000 Hz, mono, 16-bit PCM, 93,525 frames, 3.896875 seconds;
- output SHA-256:
  `00a121b6aa419772f4e99ca2be663afbe7a0f3d4c6e0ab21e00e177d60afc63c`;
- result: `verified=true`, `verified_to=qwen3_rust_synthesized_wav`.

This proves local model integrity, Metal loading, and Rust synthesis only. It
does not prove intelligibility, speaker quality, physical playback, or human
audibility.

### File-level STT and playback follow-up

The same named artifact was transcribed locally with the existing macOS
Whisper path. The cached `base` model returned:

`你好,这是Agent Bridge的全热的语音试验。`

The normalized word overlap was `0.846`, above the existing `0.8`
`SYNTH_FILE_INTEL_MIN` threshold, so file-level intelligibility is accepted.
The cached `tiny` model returned only `0.538` overlap and is recorded as a
degraded detector, not as a rejection of the audio. `large-v3-turbo` exceeded
the 45-second local STT timeout and remains unavailable for this short gate.

The exact artifact was then sent once to `/usr/bin/afplay`; the process exited
zero after 4.649 seconds. The owner reported hearing this artifact and judged
the voice "非常棒！柔美！". This closes the disposable human-audibility and
quality observation for this named artifact, while keeping the scope limited:
it is not a claim of aggregate delivery reliability or production integration.

## Required next gate

1. ~~Fetch the official model on a node or network path with adequate
   object-store bandwidth, then transfer the two files to the Mac.~~ Done via
   the verified ModelScope snapshot above; the files remain outside Git.
2. ~~Run the patched arm64 CLI with `--device metal --dtype f16`.~~ Done.
3. ~~Generate a short fixed Chinese utterance with a fixed seed.~~ Done.
4. ~~Record wall time, output SHA-256, sample rate, channels, and duration.~~
   Done. Peak-memory measurement remains optional and unclaimed.
5. ~~Run file-level STT as an intelligibility check.~~ Done with cached
   Whisper `base`, overlap `0.846`.
6. ~~Play the named artifact and obtain human audibility confirmation.~~ Done:
   `afplay` completed and the owner confirmed hearing the artifact as
   "非常棒！柔美！".
7. Only then design a default-off `qwen3-rust` Agent-Bridge backend. Keep
   generated models and audio outside Git.

## Offline gate implementation

`scripts/qwen3_tts_rust_gate.py` makes steps 1-4 fail closed:

- embeds the pinned Hugging Face revision and complete LFS SHA-256 identities;
- verifies exact size before hashing either large file;
- refuses to execute when either model file is absent or mismatched;
- invokes only a local model path with fixed `metal`, `f16`, Chinese language,
  and deterministic seed parameters;
- refuses to overwrite an existing output;
- records command timing, bounded process output, WAV shape, bytes, and SHA-256;
- supports explicit `0.6b-customvoice` and `1.7b-customvoice` manifests, with
  profile-specific speaker defaults;
- verifies only to `qwen3_rust_synthesized_wav`, never to STT, speaker output,
  or human audibility.

Example after both model files have been transferred:

```bash
python3 scripts/qwen3_tts_rust_gate.py \
  --binary /private/tmp/ab-qwen3-rust-pilot/bin/qwen-tts \
  --model-dir /private/tmp/ab-qwen3-rust-pilot/models/Qwen3-TTS-12Hz-0.6B-CustomVoice \
  --output /private/tmp/ab-qwen3-rust-pilot/out/qwen3-rust-zh.wav
```

The implementation has eight unit tests covering missing files, size mismatch,
same-size SHA mismatch, fixed Metal command shape, successful non-empty WAV
attestation, existing-output preservation, timeout honesty, and the explicit
1.7B profile. A negative run
against the current incomplete disposable model returned
`model_integrity_failed` with `execution.attempted=false`.
