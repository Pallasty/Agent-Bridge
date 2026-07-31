# Voice Scene S0 contract

Voice Scene is Agent-Bridge's shared event contract for story performance,
meeting reconstruction, and multi-agent theatre. S0 defines the data and
validation boundary only. It does not synthesize or record audio, load models,
write memories or forum posts, or mutate a running Agent-Bridge instance.

## Static commands

```bash
python3 scripts/voice_scene_contract.py validate \
  docs/design/voice-scene/fixtures/story.json --pretty

python3 scripts/voice_scene_contract.py plan \
  docs/design/voice-scene/fixtures/meeting.json --pretty
```

Both commands read one JSON document and print JSON to stdout. `validate`
returns a non-zero status for semantic contract violations. `plan` returns a
bounded summary whose status is `contract_ready_no_runtime`.

## S0 acceptance surface

- One schema covers `story`, `meeting`, and `agent_theater`.
- Sources carry exact content hashes and explicit versions.
- Timeline order and idempotency keys are deterministic and validated.
- Speaker identity and versioned voice profiles are separate.
- Claims distinguish source truth, observation, inference, and simulation.
- Simulation branches cannot write into the canonical branch.
- Every runtime-effect flag is required to be `false`.

The JSON Schema checks document shape. The Python validator checks
cross-reference and provenance invariants that JSON Schema alone cannot
express. A packet is S0-valid only when it passes both.

## Files

- `voice_scene.schema.json`: Draft 2020-12 interchange schema.
- `story_plan.schema.json`: S1 static story-ingest and review schema.
- `story_render_manifest.schema.json`: S2 segment/chapter render evidence.
- `character_state.schema.json`: S3 ledger and resume snapshot contract.
- `realtime_interaction.schema.json`: S4 PTT turn receipt and owner gates.
- `voice_audition.schema.json`: S5 blinded three-voice audition plan.
- `sherpa_render_pack.schema.json`: S5B atomic render and ASR receipt.
- `voice_backend_capabilities.json`: S5 backend provenance and capability matrix.
- `fixtures/story.json`: novel-performance contract example.
- `fixtures/story_s1.md`: deterministic TXT/Markdown ingest sample.
- `fixtures/meeting.json`: meeting reconstruction contract example.
- `fixtures/agent_theater.json`: multi-agent scene contract example.
- `ADR-0001-voice-scene-contract.md`: architecture decision and boundaries.
- `NOVEL_TTS_V1_MIGRATION.md`: mapping from the existing novel prototype.
- `ADR-0003-story-offline-render.md`: cache, assembly, and playback gates.
- `ADR-0004-memory-grounded-character-state.md`: knowledge and branch gates.
- `ADR-0005-realtime-story-interaction.md`: realtime state and consent gates.
- `ADR-0006-chinese-multispeaker-audition.md`: S5 audition and promotion gates.
- `ADR-0007-sherpa-render-asr-gate.md`: S5B integrity and atomic render gate.
- `ADR-0008-mi50-container-and-community-onnx-research-gate.md`: S5D
  static research and isolation gates.
- `voice_snapshot_static_audit.schema.json`: S5G downloaded-snapshot static
  audit receipt.
- `voice_cpu_int4_smoke_receipt.schema.json`: S5H CPU INT4 session-creation
  receipt with no graph execution.
- `voice_cpu_int4_numeric_probe.schema.json`: S5I bounded codec-embedding
  numeric probe receipt.
- `voice_cpu_int4_predictor_probe.schema.json`: S5J bounded code-predictor
  numeric probe receipt.

## S5 Chinese multi-speaker audition

`scripts/story_voice_audition.py` defines the static S5A gate. It validates
backend capability and license posture, creates a deterministic blinded plan
for narrator plus two distinct characters, computes Chinese ASR character error
rate, and evaluates explicit owner review receipts.

S5A does not install a backend, download a runtime model, render or play audio,
or bind a speaker to a character. AISHELL-3 remains local-evaluation-only while
its model-weight license is unverified. Full S5 exit requires three real,
hash-bound artifacts and owner confirmation.

## S5B integrity-gated render pack

`scripts/story_sherpa_render_gate.py` verifies the complete AISHELL-3 asset
manifest and an isolated synthesis binary before rendering. It publishes a
three-file pack atomically, refuses existing output directories, validates PCM
WAV shape, and binds file-level Chinese ASR results and CER into one receipt.

The machine-verified pack is not played automatically. Its speaker IDs remain
opaque until a separate owner-authorized blind audition records audibility,
naturalness, role fit, and pairwise distinguishability.

## S5D voice-model research gate

`scripts/story_voice_model_research_gate.py` performs a static, non-actuating
audit of an MI50 container configuration and experimental voice-model
manifest. It fails closed for broad GPU exposure, privileged containers,
unpinned images, runtime networking, writable root filesystems, or incomplete
community ONNX evidence.

S5E adds an inert least-privilege profile,
`mi50_qwen_onnx.compose.yaml`, and a metadata-only supply-chain snapshot for
the selected Qwen3-TTS streaming ONNX conversion. The profile cannot infer:
its runtime opt-in is false and its entrypoint is `/bin/false`. The snapshot
does not treat a model-card license declaration, remote file listing, or
historical revision as verified model weights.

S5F uses `scripts/story_voice_small_file_audit.py` for an owner-authorized,
fixed-revision, small-file-only acquisition. It never imports the downloaded
Python. Failed or incomplete acquisition leaves no final evidence directory.
The current fixed-revision transport result is recorded in
`s5f_small_file_acquisition_evidence.json`.

S5G uses `scripts/story_voice_snapshot_audit.py` for a separately downloaded
ModelScope snapshot. It streams complete file hashes, validates all six
variant manifests, scans Python with `ast`, and optionally parses ONNX protobuf
graphs with external tensor loading disabled. The current 1.7B CustomVoice
receipt is `s5g_modelscope_snapshot_static_audit.json`. Its status is blocked,
not trial-ready: ModelScope supplied mutable `master`, the snapshot lacks a
standalone license file, and a build utility contains a subprocess primitive.
The advertised CUDA execution provider is not evidence of MI50 support.

S5H uses `scripts/story_voice_cpu_int4_smoke_gate.py` to create isolated
ONNX Runtime sessions for only the seven graphs referenced by the CPU INT4
manifest. It pins `CPUExecutionProvider`, disables graph optimization, and
never calls `session.run()`. The current receipt,
`s5h_cpu_int4_session_smoke.json`, records successful session creation for all
seven graphs under ONNX Runtime 1.28.0. This is a compatibility precheck only:
it does not execute inference, synthesize audio, clear S5G supply-chain
blockers, or imply ROCm/MI50 support.

S5I uses `scripts/story_voice_cpu_int4_numeric_probe.py` to execute only the
CPU INT4 `codec_embed` graph twice with fixed synthetic IDs `[0,1,2,3]`. The
current `s5i_cpu_int4_codec_embed_numeric_probe.json` receipt records a finite,
deterministic `float32[1,4,2048]` output. The embedding is not forwarded to any
autoregressive or waveform graph, so this stage produces no token stream or
audio and makes no quality, parity, performance, or MI50 claim.

S5J uses `scripts/story_voice_cpu_int4_predictor_probe.py` to execute only the
CPU INT4 `code_predictor` graph with zero-valued hidden-state and codec-ID
fixtures. The current `s5j_cpu_int4_code_predictor_probe.json` receipt records
finite, deterministic `float32[1,15,2048]` logits. The probe performs no
argmax, sampling, recurrence, token generation, or audio work; it is graph
numerics evidence, not a generation or quality claim.

S5K uses `scripts/story_voice_cpu_int4_talker_cache_probe.py` to execute one
zero-history step of the CPU INT4 `talker_cache` graph with a bounded,
deterministic nonzero embedding. The
`s5k_cpu_int4_talker_cache_probe.json` receipt validates against
`voice_cpu_int4_talker_cache_probe.schema.json` and records nonzero finite
logits, a finite hidden state, 56 finite present-cache tensors, and identical
aggregate hashes across two runs. The cache is not fed back and the probe
performs no sampling, recurrence, token generation, waveform decoding, audio,
GPU work, or community-Python import.

S5L uses `scripts/story_voice_cpu_int4_cache_feedback_probe.py` to run two
independent copies of an exactly two-step CPU sequence. Within each sequence,
the first step's 56 present KV tensors are fed back once with position one and
a two-token attention mask. The
`s5l_cpu_int4_cache_feedback_probe.json` receipt validates against
`voice_cpu_int4_cache_feedback_probe.schema.json` and records deterministic
cache growth from `[1,8,1,128]` to `[1,8,2,128]`. The second embedding remains
a synthetic fixture rather than a sampled/model-derived token representation;
no sampling, further recurrence, decoding, audio, GPU work, or
community-Python import occurs.

S5M uses `scripts/story_voice_cpu_int4_residual_embed_probe.py` to execute only
the CPU INT4 `residual_embed` graph twice with the fixed synthetic codec IDs
`[0..15]`. The `s5m_cpu_int4_residual_embed_probe.json` receipt validates
against `voice_cpu_int4_residual_embed_probe.schema.json` and records a finite,
nonzero, deterministic `float32[1,2048]` step embedding. The output is not
forwarded, so this remains isolated graph evidence rather than a generated
codec frame or connected autoregressive path.

S5N uses `scripts/story_voice_cpu_int4_single_frame_loop_probe.py` to connect
the CPU INT4 talker cache, code predictor, and residual embed graphs for one
raw-greedy codec frame and one cache feedback. The
`s5n_cpu_int4_single_frame_loop_probe.json` receipt validates against
`voice_cpu_int4_single_frame_loop_probe.schema.json`, records the selected
16-code frame, and binds deterministic full-sequence hashes. Because this
snapshot lacks local model configuration, the probe applies no codec-EOS or
reserved-token suppression and explicitly makes no reference-generation
equivalence claim. It stops before a second frame, waveform decoding, audio,
GPU work, or community-Python import.

S5O uses `scripts/story_voice_config_provenance_gate.py` to hash-check an
official Qwen configuration observed through ModelScope and reconcile it with
fresh metadata from the three CPU INT4 graphs. The
`s5o_config_provenance_gate.json` receipt validates against
`voice_config_provenance_gate.schema.json`. All model dimensions and codec
IDs match the graph contracts, but the converter did not record its upstream
revision, ModelScope exposed only mutable `master`, and fixed-revision
Hugging Face raw transfer was unavailable. The receipt therefore retains
`reference_generation_ready=false` and blocks reference-compatible
multi-frame claims despite structural compatibility.

S5P uses `scripts/story_voice_provenance_remediation_decision.py` to make the
next provenance action executable and fail closed. Published converter
evidence identifies the official base model but does not bind the current ONNX
artifacts to an upstream revision, so path A cannot currently close lineage.
The decision selects path B: an isolated re-export from immutable official
Qwen commit `6c3e96b6a2c593ce3e546ee699a5d944de81850e`, beginning with a CPU FP32
reference lane before quantization comparison. Path A remains reopenable only
with artifact-bound publisher evidence. The
`s5p_provenance_remediation_decision.json` receipt records no downloads,
converter or graph execution, snapshot replacement, GPU use, playback, or
global memory/forum writes. Weight acquisition and every later adoption step
remain separately authorized; `reference_generation_ready=false`.

S5Q uses `scripts/story_voice_fixed_source_acquisition_plan.py` to produce a
revision-pinned, small-file-only offline acquisition packet. Its explicit
11-path allowlist contains no `.safetensors`; no weight command is emitted.
The isolated destination is outside the current ModelScope ONNX snapshot, and
the planner fails closed on an existing/overlapping destination or less than
the 128 GiB workspace policy floor. Because fixed-revision Hugging Face
transport remains unavailable on this host, the SHA-256 ledger stays pending
until offline acquisition rather than being inferred from mutable files. The
`s5q_fixed_source_acquisition_plan.json` receipt records zero network,
filesystem-creation, model-execution, GPU, and playback effects.

## S4 realtime story interaction

`scripts/story_realtime_interaction.py` provides a bounded push-to-talk turn
orchestrator. It pauses the story, captures only with explicit microphone
authorization, routes the stable transcript through S3 grounding and spoiler
checks, renders a response, emits it only under a separate output gate, and
resumes the exact playback position.

Fixture tests do not open a microphone or sound device. A real closed-loop
trial remains a separate explicit owner-authorized acceptance action.

For retained session artifacts, `withdraw_artifacts()` requires separate owner
authorization and deletes only the explicitly named files; directories and
unrelated session files are never recursively removed.

## S3 memory-grounded character state

`scripts/story_character_state.py` provides append-only canon, character
knowledge, and interaction ledgers; cursor-bounded `/story ask`; a spoiler
falsifier; inferential psychological profiles; and deterministic session
snapshot/resume projections.

```bash
python3 scripts/story_character_state.py /story ask \
  --snapshot docs/design/voice-scene/fixtures/s3/character_state.json \
  --character character_lin \
  --question '钥匙在哪里？'
```

S3 is text-only. Story state snapshots retain
`proposal_only_owner_review_required` and do not silently write simulations or
unreviewed story facts into global AB memory.

## S2 offline render

`scripts/story_offline_render.py` provides the render-only contract,
version-bound segment cache, bounded retry, PCM WAV validation, chapter
assembly, integrity verification, and `ChapterPlayer` state machine.

Playback is never implicit. `ChapterPlayer.start()` and `.resume()` require an
explicit owner authorization argument. Machine-verified WAV output remains
`human_audition=pending` until the owner listens to that exact artifact.

## S1 static story ingest

```bash
python3 scripts/story_static_ingest.py \
  /story docs/design/voice-scene/fixtures/story_s1.md chapter 2 --pretty
```

The command prints a deterministic, reviewable story plan. It does not create
an output file. Character, relationship, event, and emotion extraction is
deliberately heuristic and remains in `needs_review`.
